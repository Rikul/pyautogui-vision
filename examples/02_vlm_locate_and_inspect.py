"""
Example 2: VLM Visual Grounding & Screen Inspection.
Demonstrates locating UI elements by natural language description and asking questions
about the screen using any OpenAI-compatible Vision-Language Model.

Run with:
    uv run python examples/02_vlm_locate_and_inspect.py
"""

import os
import pyautogui


def load_dotenv_if_present(path=".env"):
    """Lightweight .env loader so no extra dependency is needed."""
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main():
    load_dotenv_if_present()

    # Configure VLM (reads PYAUTOGUI_VLM_* from environment by default, or pass explicitly)
    pyautogui.configure_vlm(
        base_url=os.environ.get("PYAUTOGUI_VLM_BASE_URL", "http://localhost:11434/v1"),
        api_key=os.environ.get("PYAUTOGUI_VLM_API_KEY") or os.environ.get("OPENAI_API_KEY", "ollama"),
        model=os.environ.get("PYAUTOGUI_VLM_MODEL", "qwen2.5-vl"),
    )
    print("VLM Configuration:", pyautogui.get_vlm_config())

    # 1. Ask the VLM to describe the current screen state
    print("\nInspecting current screen with VLM...")
    summary = pyautogui.vlm_inspect(
        "Briefly describe what application is in focus and list 3 interactive UI elements visible on screen."
    )
    print("\nVLM Screen Summary:\n", summary)

    # 2. Locate a UI element by natural-language description
    target_query = "the search bar or address bar"
    print(f"\nSearching for {target_query!r} on screen...")
    box = pyautogui.locateOnScreen(target_query)
    if box is not None:
        pt = pyautogui.center(box)
        print(f"Found {target_query!r} at {box} -> center={pt}")
        # To click it directly, you can also call:
        # pyautogui.click("the search bar or address bar")
    else:
        print(f"Could not find {target_query!r} on the current screen.")


if __name__ == "__main__":
    main()
