"""
Example 3: Executing Compound Natural-Language Instructions with pyautogui.perform().
Demonstrates how a single natural-language instruction can locate fields, click,
type text, and press keys in a multi-step VLM observe-act loop.

Run with:
    uv run python examples/03_perform_natural_language.py "type in my name 'Alice' in the first name field and hit enter"
"""

import os
import sys
import pyautogui


def load_dotenv_if_present(path=".env"):
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def on_step_callback(step_info):
    print(
        f"  [Step {step_info['step']}] Executed {step_info['tool']}({step_info['arguments']}) "
        f"-> {step_info['result'].get('status')}"
    )


def main():
    load_dotenv_if_present()

    pyautogui.configure_vlm(
        base_url=os.environ.get("PYAUTOGUI_VLM_BASE_URL", "http://localhost:11434/v1"),
        api_key=os.environ.get("PYAUTOGUI_VLM_API_KEY") or os.environ.get("OPENAI_API_KEY", "ollama"),
        model=os.environ.get("PYAUTOGUI_VLM_MODEL", "qwen2.5-vl"),
    )

    instruction = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "type in my name 'Alice' in the first name field and hit enter"
    )

    print(f"Executing instruction: {instruction!r}")
    print("(Move mouse to any screen corner to trigger PyAutoGUI FAILSAFE)\n")

    result = pyautogui.perform(
        instruction=instruction,
        max_steps=8,
        draw_grid=True,       # Overlays a coordinate grid to help the VLM read exact pixels
        confirm=False,        # Set confirm=True to prompt before each mouse/keyboard action
        on_step=on_step_callback,
    )

    print("\n--- Result ---")
    print(f"Success: {result.success}")
    print(f"Summary: {result.summary}")
    print(f"Total Steps Executed: {len(result.steps)}")


if __name__ == "__main__":
    main()
