"""
Example 1: Fast Screen Capture (mss), Pixel Inspection, and Mouse/Keyboard Basics.
Works across Windows, macOS, Linux, and WSL (controlling the Windows host desktop).

Run with:
    uv run python examples/01_basic_mouse_keyboard_mss.py
"""

import time
import pyautogui
from pyautogui.agent import capture_for_vlm, get_screen_state


def main():
    print("--- PyAutoGUI Environment Info ---")
    print(f"Platform: {pyautogui.sys.platform} (WSL={pyautogui.IS_WSL})")
    state = get_screen_state()
    print(f"Screen Size: {state['screen_width']}x{state['screen_height']}")
    print(f"Cursor Position: ({state['cursor_x']}, {state['cursor_y']})")
    print(f"Active Window: {state['active_window']}")

    # 1. Fast screenshot via mss
    t0 = time.perf_counter()
    im = pyautogui.screenshot()
    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(f"\nCaptured {im.size[0]}x{im.size[1]} screenshot via mss in {elapsed_ms:.1f} ms")

    # 2. Inspect pixel at current cursor position
    cur_x, cur_y = pyautogui.position()
    rgb = pyautogui.pixel(cur_x, cur_y)
    print(f"Pixel RGB at cursor ({cur_x}, {cur_y}): {rgb}")

    # 3. Capture an annotated screenshot (with cursor crosshair & coordinate grid) for VLM debugging
    snap = capture_for_vlm(draw_cursor=True, draw_grid=True, grid_step=200)
    output_path = "annotated_preview.png"
    snap["image"].save(output_path)
    print(f"Saved annotated VLM preview (with cursor crosshair + coordinate grid) to {output_path}")


if __name__ == "__main__":
    main()
