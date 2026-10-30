# OpenAI Function Calling / JSON Schema tool definitions and execution dispatcher for PyAutoGUI.
# Provides inspection, mouse, and keyboard tools for VLM agents and perform().
# BSD license

import json
import pyautogui
from pyautogui.agent.inspector import capture_for_vlm, get_screen_state


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "inspect_screen",
            "description": "Capture an updated screenshot of the screen along with current mouse cursor position, screen resolution, and active window title.",
            "parameters": {
                "type": "object",
                "properties": {
                    "draw_grid": {
                        "type": "boolean",
                        "description": "Overlay a coordinate grid on the screenshot to help read exact (x, y) pixel coordinates.",
                        "default": False,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "locate_element",
            "description": "Use visual grounding to find the bounding box and center (x, y) coordinates of a UI element described in natural language.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Natural language description of the UI element to find (e.g. 'the First Name text input field', 'the blue Submit button').",
                    }
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mouse_click",
            "description": "Click the mouse at specific (x, y) pixel coordinates OR on a UI element described by 'target'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "integer",
                        "description": "X pixel coordinate on screen to click.",
                    },
                    "y": {
                        "type": "integer",
                        "description": "Y pixel coordinate on screen to click.",
                    },
                    "target": {
                        "type": "string",
                        "description": "Optional natural language description of the UI element to click if x and y are not provided.",
                    },
                    "button": {
                        "type": "string",
                        "enum": ["left", "middle", "right", "primary", "secondary"],
                        "description": "Mouse button to click.",
                        "default": "primary",
                    },
                    "clicks": {
                        "type": "integer",
                        "description": "Number of clicks (1 for single click, 2 for double click, 3 for triple click).",
                        "default": 1,
                    },
                    "duration": {
                        "type": "number",
                        "description": "Duration in seconds to move the mouse to the target before clicking.",
                        "default": 0.0,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mouse_move",
            "description": "Move the mouse cursor to absolute (x, y) coordinates or by relative (dx, dy) offsets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "Absolute X coordinate."},
                    "y": {"type": "integer", "description": "Absolute Y coordinate."},
                    "dx": {"type": "integer", "description": "Relative horizontal offset if x/y are omitted."},
                    "dy": {"type": "integer", "description": "Relative vertical offset if x/y are omitted."},
                    "duration": {"type": "number", "description": "Movement duration in seconds.", "default": 0.0},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mouse_drag",
            "description": "Drag the mouse from its current position (or start_x, start_y) to destination (x, y).",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "Destination X coordinate."},
                    "y": {"type": "integer", "description": "Destination Y coordinate."},
                    "start_x": {"type": "integer", "description": "Optional starting X coordinate."},
                    "start_y": {"type": "integer", "description": "Optional starting Y coordinate."},
                    "button": {
                        "type": "string",
                        "enum": ["left", "middle", "right", "primary", "secondary"],
                        "default": "primary",
                    },
                    "duration": {"type": "number", "description": "Drag duration in seconds.", "default": 0.2},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mouse_scroll",
            "description": "Scroll the mouse wheel vertically or horizontally.",
            "parameters": {
                "type": "object",
                "properties": {
                    "clicks": {
                        "type": "integer",
                        "description": "Amount to scroll (positive for up/right, negative for down/left).",
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["vertical", "horizontal"],
                        "default": "vertical",
                    },
                    "x": {"type": "integer", "description": "Optional X coordinate to place cursor before scrolling."},
                    "y": {"type": "integer", "description": "Optional Y coordinate to place cursor before scrolling."},
                },
                "required": ["clicks"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "keyboard_type",
            "description": "Type a string of text into the currently focused field, optionally clicking a target or coordinates first and/or pressing Enter afterwards.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text string to type."},
                    "x": {"type": "integer", "description": "Optional X coordinate to click before typing."},
                    "y": {"type": "integer", "description": "Optional Y coordinate to click before typing."},
                    "target": {
                        "type": "string",
                        "description": "Optional natural language description of the input field to click before typing.",
                    },
                    "press_enter": {
                        "type": "boolean",
                        "description": "If true, press the Enter key after typing the text.",
                        "default": False,
                    },
                    "clear_first": {
                        "type": "boolean",
                        "description": "If true, select all (Ctrl+A) and Backspace before typing.",
                        "default": False,
                    },
                    "interval": {
                        "type": "number",
                        "description": "Delay in seconds between each keystroke.",
                        "default": 0.0,
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "keyboard_press",
            "description": "Press and release one or more special or character keys in sequence (e.g. 'enter', 'tab', 'esc', 'down', 'backspace').",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "anyOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ],
                        "description": "A key name (e.g. 'enter') or list of key names (e.g. ['tab', 'tab', 'enter']).",
                    },
                    "presses": {
                        "type": "integer",
                        "description": "Number of times to repeat the key press.",
                        "default": 1,
                    },
                },
                "required": ["keys"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "keyboard_hotkey",
            "description": "Press a keyboard shortcut combination simultaneously (e.g. ['ctrl', 'c'], ['ctrl', 'shift', 'esc'], ['alt', 'f4']).",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ordered list of modifier and key names to press together.",
                    }
                },
                "required": ["keys"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pixel_color",
            "description": "Return the RGB color of the screen pixel at (x, y).",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate."},
                    "y": {"type": "integer", "description": "Y coordinate."},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait",
            "description": "Pause execution for a specified number of seconds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "number", "description": "Seconds to wait."}
                },
                "required": ["seconds"],
            },
        },
    },
]


def execute_tool(name, arguments):
    """
    Execute a PyAutoGUI agent tool by ``name`` with ``arguments`` (a dict or JSON string).
    Returns a dictionary with ``status`` ("ok" or "error") and tool-specific result data.
    """
    if isinstance(arguments, str):
        arguments = json.loads(arguments) if arguments.strip() else {}
    elif arguments is None:
        arguments = {}

    if name == "inspect_screen":
        draw_grid = bool(arguments.get("draw_grid", False))
        snap = capture_for_vlm(draw_cursor=True, draw_grid=draw_grid)
        return {
            "status": "ok",
            "action": "inspect_screen",
            "state": snap["state"],
            "mime_type": snap["mime_type"],
            "base64_jpeg": snap["base64_jpeg"],
            "base64_png": snap["base64_png"],
        }

    elif name == "locate_element":
        target = arguments["target"]
        box = pyautogui.vlm_locate(target)
        if box is None:
            return {"status": "not_found", "target": target}
        pt = pyautogui.center(box)
        return {
            "status": "ok",
            "target": target,
            "box": {"left": box.left, "top": box.top, "width": box.width, "height": box.height},
            "center": {"x": pt.x, "y": pt.y},
        }

    elif name == "mouse_click":
        x = arguments.get("x")
        y = arguments.get("y")
        target = arguments.get("target")
        button = arguments.get("button", pyautogui.PRIMARY)
        clicks = int(arguments.get("clicks", 1))
        duration = float(arguments.get("duration", 0.0))

        if x is None and y is None and target:
            pt = pyautogui.locateCenterOnScreen(target)
            if pt is None:
                return {"status": "error", "error": "Could not locate target on screen: %r" % (target,)}
            x, y = pt.x, pt.y

        pyautogui.click(x=x, y=y, clicks=clicks, button=button, duration=duration)
        cur = pyautogui.position()
        return {"status": "ok", "action": "mouse_click", "x": cur.x, "y": cur.y, "button": button, "clicks": clicks}

    elif name == "mouse_move":
        x = arguments.get("x")
        y = arguments.get("y")
        dx = arguments.get("dx")
        dy = arguments.get("dy")
        duration = float(arguments.get("duration", 0.0))

        if x is not None or y is not None:
            pyautogui.moveTo(x=x, y=y, duration=duration)
        else:
            pyautogui.moveRel(xOffset=dx or 0, yOffset=dy or 0, duration=duration)
        cur = pyautogui.position()
        return {"status": "ok", "action": "mouse_move", "x": cur.x, "y": cur.y}

    elif name == "mouse_drag":
        start_x = arguments.get("start_x")
        start_y = arguments.get("start_y")
        x = int(arguments["x"])
        y = int(arguments["y"])
        button = arguments.get("button", pyautogui.PRIMARY)
        duration = float(arguments.get("duration", 0.2))

        if start_x is not None and start_y is not None:
            pyautogui.moveTo(int(start_x), int(start_y))
        pyautogui.dragTo(x, y, duration=duration, button=button)
        cur = pyautogui.position()
        return {"status": "ok", "action": "mouse_drag", "x": cur.x, "y": cur.y}

    elif name == "mouse_scroll":
        clicks = int(arguments["clicks"])
        direction = arguments.get("direction", "vertical")
        x = arguments.get("x")
        y = arguments.get("y")
        if direction == "horizontal":
            pyautogui.hscroll(clicks, x=x, y=y)
        else:
            pyautogui.vscroll(clicks, x=x, y=y)
        return {"status": "ok", "action": "mouse_scroll", "clicks": clicks, "direction": direction}

    elif name == "keyboard_type":
        text = arguments["text"]
        x = arguments.get("x")
        y = arguments.get("y")
        target = arguments.get("target")
        press_enter = bool(arguments.get("press_enter", False))
        clear_first = bool(arguments.get("clear_first", False))
        interval = float(arguments.get("interval", 0.0))

        if x is not None and y is not None:
            pyautogui.click(int(x), int(y))
        elif target:
            pt = pyautogui.locateCenterOnScreen(target)
            if pt is None:
                return {"status": "error", "error": "Could not locate input field: %r" % (target,)}
            pyautogui.click(pt.x, pt.y)

        if clear_first:
            pyautogui.hotkey("ctrl", "a")
            pyautogui.press("backspace")

        pyautogui.typewrite(text, interval=interval)
        if press_enter:
            pyautogui.press("enter")

        return {
            "status": "ok",
            "action": "keyboard_type",
            "text": text,
            "press_enter": press_enter,
        }

    elif name == "keyboard_press":
        keys = arguments["keys"]
        presses = int(arguments.get("presses", 1))
        pyautogui.press(keys, presses=presses)
        return {"status": "ok", "action": "keyboard_press", "keys": keys, "presses": presses}

    elif name == "keyboard_hotkey":
        keys = arguments["keys"]
        pyautogui.hotkey(*keys)
        return {"status": "ok", "action": "keyboard_hotkey", "keys": keys}

    elif name == "get_pixel_color":
        x = int(arguments["x"])
        y = int(arguments["y"])
        rgb = pyautogui.pixel(x, y)
        return {"status": "ok", "x": x, "y": y, "rgb": [rgb.red, rgb.green, rgb.blue]}

    elif name == "wait":
        seconds = float(arguments["seconds"])
        pyautogui.sleep(seconds)
        return {"status": "ok", "action": "wait", "seconds": seconds}

    else:
        raise pyautogui.PyAutoGUIException("Unknown agent tool: %r" % (name,))
