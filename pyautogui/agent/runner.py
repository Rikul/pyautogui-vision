# Multi-step and compound-instruction VLM agent runner for PyAutoGUI.
# Powers pyautogui.perform("type in my name in the first name field and hit enter").
# BSD license

import collections
import json

import pyautogui
from pyautogui._vlm import _extract_json_from_text, chat_completion
from pyautogui.agent.inspector import capture_for_vlm
from pyautogui.agent.tools import TOOLS, execute_tool

PerformResult = collections.namedtuple("PerformResult", "success summary steps")


_SYSTEM_PROMPT = """You are an autonomous GUI automation agent controlling a desktop via PyAutoGUI.
You are given a screenshot of the current screen (with a red crosshair marking the current mouse cursor) and a user instruction.

Use the provided tools (`mouse_click`, `keyboard_type`, `keyboard_press`, `keyboard_hotkey`, `mouse_move`, `mouse_drag`, `mouse_scroll`, `locate_element`, `inspect_screen`, `wait`) to complete the user's instruction accurately.

Guidelines:
1. If you can see the target UI element(s) in the screenshot, you may emit all necessary tool calls in sequence (for example, calling `keyboard_type(x=..., y=..., text="...", press_enter=true)` or `mouse_click(x=..., y=...)` followed by `keyboard_type(text="...", press_enter=true)`).
2. If an action opens a new menu, dialog, or page that you need to see before continuing, perform the first action and then wait for the updated screenshot on the next turn.
3. Once the instruction has been completely fulfilled, respond with a brief final summary message and no further tool calls."""


def _parse_fallback_actions_from_text(content):
    """
    If a local VLM does not support native OpenAI `tool_calls` and instead outputs JSON in its text response,
    extract any `{"tool": "...", "arguments": {...}}` or `[{"name": "...", "arguments": {...}}]` items.
    """
    parsed = _extract_json_from_text(content)
    if not parsed:
        return []
    items = parsed if isinstance(parsed, list) else [parsed]
    calls = []
    for idx, item in enumerate(items):
        if isinstance(item, dict):
            fn_name = item.get("tool") or item.get("name") or item.get("action")
            fn_args = item.get("arguments") or item.get("args") or item.get("parameters") or {}
            if fn_name and any(t["function"]["name"] == fn_name for t in TOOLS):
                calls.append(
                    {
                        "id": "fallback_call_%d" % idx,
                        "type": "function",
                        "function": {
                            "name": fn_name,
                            "arguments": json.dumps(fn_args) if isinstance(fn_args, dict) else str(fn_args),
                        },
                    }
                )
    return calls


def perform(
    instruction,
    max_steps=10,
    draw_grid=False,
    confirm=False,
    on_step=None,
    settle_delay=None,
):
    """
    Execute a natural-language GUI instruction (including compound multi-action instructions
    such as ``"type in my name in the first name field and hit enter"``) using the configured VLM
    and PyAutoGUI's inspection, mouse, and keyboard tools.

    Args:
      instruction (str): Natural language instruction to perform on the desktop.
      max_steps (int, optional): Maximum number of VLM observe-act turns (default 10).
      draw_grid (bool, optional): If True, overlays a coordinate grid on screenshots sent to the VLM.
      confirm (bool or callable, optional): If True, prompts via ``pyautogui.confirm()`` before each tool call.
        If a callable ``confirm(tool_name, tool_args) -> bool``, calls it to approve each action.
      on_step (callable, optional): Optional callback ``on_step(step_dict)`` invoked after each tool execution.
      settle_delay (float, optional): Seconds to wait after each GUI action so windows/menus/focus can settle
        (defaults to ``PYAUTOGUI_SETTLE_DELAY`` env var or ``0.35`` seconds).

    Returns:
      ``PerformResult(success, summary, steps)``
    """
    snap = capture_for_vlm(draw_cursor=True, draw_grid=draw_grid)
    state = snap["state"]

    initial_user_content = [
        {
            "type": "text",
            "text": (
                "Instruction: %s\n"
                "Screen resolution: %dx%d | Current cursor: (%d, %d) | Active window: %s"
                % (
                    instruction,
                    state["screen_width"],
                    state["screen_height"],
                    state["cursor_x"],
                    state["cursor_y"],
                    state["active_window"] or "Unknown",
                )
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": "data:%s;base64,%s" % (snap["mime_type"], snap["base64_image"])},
        },
    ]

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": initial_user_content},
    ]

    executed_steps = []

    for step_idx in range(max_steps):
        resp = chat_completion(messages, tools=TOOLS, tool_choice="auto", temperature=0.0)
        message = resp["choices"][0]["message"]
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls") or []

        if not tool_calls and content:
            tool_calls = _parse_fallback_actions_from_text(content)

        # If the VLM returned no tool calls, it considers the instruction complete.
        if not tool_calls:
            return PerformResult(
                success=True,
                summary=content.strip() or "Completed instruction.",
                steps=executed_steps,
            )

        # Append assistant message with tool_calls to conversation history
        assistant_msg = {"role": "assistant", "content": content or None, "tool_calls": tool_calls}
        messages.append(assistant_msg)

        for tc in tool_calls:
            tc_id = tc.get("id", "call_%d" % len(executed_steps))
            fn_spec = tc.get("function", {})
            fn_name = fn_spec.get("name", "")
            raw_args = fn_spec.get("arguments", "{}")
            parsed_args = json.loads(raw_args) if isinstance(raw_args, str) and raw_args.strip() else (raw_args or {})

            # Optional human-in-the-loop confirmation
            if confirm:
                if callable(confirm):
                    approved = confirm(fn_name, parsed_args)
                else:
                    ans = pyautogui.confirm(
                        "Allow PyAutoGUI agent to execute %s(%s)?" % (fn_name, json.dumps(parsed_args))
                    )
                    approved = ans == "OK"
                if not approved:
                    return PerformResult(
                        success=False,
                        summary="Action %s was cancelled by user confirmation." % fn_name,
                        steps=executed_steps,
                    )

            try:
                result = execute_tool(fn_name, parsed_args, settle_delay=settle_delay)
            except pyautogui.FailSafeException:
                raise
            except Exception as exc:
                result = {"status": "error", "error": str(exc)}

            step_record = {
                "step": step_idx + 1,
                "tool": fn_name,
                "arguments": parsed_args,
                "result": result,
            }
            executed_steps.append(step_record)
            if on_step is not None:
                on_step(step_record)

            # Strip large base64 image from the tool response JSON itself and attach a fresh post-action screenshot below
            tool_reply_payload = dict(result)
            tool_reply_payload.pop("base64_image", None)
            tool_reply_payload.pop("base64_jpeg", None)
            tool_reply_payload.pop("base64_png", None)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": fn_name,
                    "content": json.dumps(tool_reply_payload),
                }
            )

        # Capture updated screen state after executing this turn's tool call(s) so the VLM can verify or continue
        new_snap = capture_for_vlm(draw_cursor=True, draw_grid=draw_grid)
        new_state = new_snap["state"]
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Updated screen after step %d. Cursor is now at (%d, %d), active window: %s. "
                            "If the instruction (%r) is now complete, reply with a final summary and no tool calls; "
                            "otherwise, continue with the remaining actions."
                            % (
                                step_idx + 1,
                                new_state["cursor_x"],
                                new_state["cursor_y"],
                                new_state["active_window"] or "Unknown",
                                instruction,
                            )
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:%s;base64,%s" % (new_snap["mime_type"], new_snap["base64_image"])},
                    },
                ],
            }
        )

    return PerformResult(
        success=False,
        summary="Reached max_steps (%d) before completion." % max_steps,
        steps=executed_steps,
    )


run_task = perform
