# Screen inspection and visual annotation utilities for VLM agents.
# Overlays cursor crosshairs and optional coordinate grids onto mss screenshots
# to improve VLM spatial grounding accuracy.
# BSD license

import pyautogui
from pyautogui._screen import screenshot
from pyautogui._vlm import encode_image_base64


def get_screen_state():
    """
    Return a dictionary of current desktop metadata: screen size, mouse cursor position,
    and active window title (if available).
    """
    width, height = pyautogui.size()
    cur_x, cur_y = pyautogui.position()
    active_title = None
    if hasattr(pyautogui, "getActiveWindowTitle"):
        try:
            active_title = pyautogui.getActiveWindowTitle()
        except Exception:
            active_title = None

    return {
        "screen_width": width,
        "screen_height": height,
        "cursor_x": cur_x,
        "cursor_y": cur_y,
        "active_window": active_title,
    }


def annotate_screenshot(pil_image, cursor_pos=None, draw_cursor=True, draw_grid=False, grid_step=200):
    """
    Draw a red crosshair at ``cursor_pos`` and/or a labeled coordinate grid onto a copy of ``pil_image``.
    Returns the annotated ``PIL.Image.Image``.
    """
    from PIL import ImageDraw

    im = pil_image.copy().convert("RGB")
    draw = ImageDraw.Draw(im)
    w, h = im.size

    if draw_grid and grid_step > 0:
        for gx in range(grid_step, w, grid_step):
            draw.line([(gx, 0), (gx, h)], fill=(180, 180, 255), width=1)
            draw.text((gx + 3, 4), str(gx), fill=(220, 40, 40))
        for gy in range(grid_step, h, grid_step):
            draw.line([(0, gy), (w, gy)], fill=(180, 180, 255), width=1)
            draw.text((4, gy + 3), str(gy), fill=(220, 40, 40))

    if draw_cursor:
        if cursor_pos is None:
            cursor_pos = pyautogui.position()
        cx, cy = int(cursor_pos[0]), int(cursor_pos[1])
        if 0 <= cx < w and 0 <= cy < h:
            r = 10
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 0, 0), width=2)
            draw.line([(cx - r - 5, cy), (cx + r + 5, cy)], fill=(255, 0, 0), width=2)
            draw.line([(cx, cy - r - 5), (cx, cy + r + 5)], fill=(255, 0, 0), width=2)

    return im


def capture_for_vlm(region=None, draw_cursor=True, draw_grid=False, grid_step=200, image_format="JPEG", quality=85):
    """
    Capture the current screen via ``mss``, annotate it for the VLM, and return a dict containing:
    - ``image``: annotated ``PIL.Image.Image``
    - ``base64_image``: base64-encoded JPEG string (also aliased as ``base64_jpeg`` and ``base64_png``)
    - ``mime_type``: ``"image/jpeg"`` (or ``"image/png"``)
    - ``state``: screen metadata dictionary from ``get_screen_state()``
    """
    state = get_screen_state()
    raw_im = screenshot(region=region)
    cursor_pos = (state["cursor_x"], state["cursor_y"])
    if region is not None:
        cursor_pos = (cursor_pos[0] - int(region[0]), cursor_pos[1] - int(region[1]))

    annotated = annotate_screenshot(
        raw_im,
        cursor_pos=cursor_pos,
        draw_cursor=draw_cursor,
        draw_grid=draw_grid,
        grid_step=grid_step,
    )
    b64 = encode_image_base64(annotated, format=image_format, quality=quality)
    mime_type = "image/jpeg" if image_format.upper() in ("JPG", "JPEG") else "image/" + image_format.lower()
    return {
        "image": annotated,
        "base64_image": b64,
        "base64_jpeg": b64,
        "base64_png": b64,
        "mime_type": mime_type,
        "state": state,
    }
