# Screen capture and pixel utilities for PyAutoGUI using mss and Pillow.
# Replaces the legacy pyscreeze dependency while delegating image recognition to VLM grounding.
# BSD license

import collections
import os
import pyautogui

Box = collections.namedtuple("Box", "left top width height")
RGB = collections.namedtuple("RGB", "red green blue")

# Global flag for backwards compatibility with useImageNotFoundException()
USE_IMAGE_NOT_FOUND_EXCEPTION = False


def center(coords):
    """
    Returns a ``Point`` object with the x and y set to an integer of the center of the rectangular region.

    The ``coords`` argument is a 4-integer tuple of (left, top, width, height).
    """
    return pyautogui.Point(int(coords[0] + coords[2] // 2), int(coords[1] + coords[3] // 2))


def screenshot(imageFilename=None, region=None, monitor=1):
    """
    Captures a screenshot using ``mss`` (or the WSL host bridge when running under WSL)
    and returns a ``PIL.Image.Image`` object.

    Args:
      imageFilename (str, optional): If provided, saves the screenshot to this path.
      region (tuple, optional): A 4-integer tuple of ``(left, top, width, height)``.
      monitor (int, optional): Monitor index for ``mss`` (1 is primary monitor, 0 is all monitors combined).
    """
    if getattr(pyautogui, "IS_WSL", False):
        return pyautogui.platformModule._screenshot(imageFilename=imageFilename, region=region)

    try:
        from PIL import Image
    except ImportError:
        raise pyautogui.PyAutoGUIException(
            "Pillow must be installed to use screenshot functions. Run: pip install Pillow"
        )

    try:
        import mss
    except ImportError:
        # Fallback to PIL.ImageGrab if mss is not yet installed in the environment
        try:
            from PIL import ImageGrab

            bbox = None
            if region is not None:
                assert len(region) == 4, "region argument must be a tuple of four ints"
                left, top, width, height = [int(v) for v in region]
                bbox = (left, top, left + width, top + height)
            im = ImageGrab.grab(bbox=bbox)
            if imageFilename is not None:
                im.save(imageFilename)
            return im
        except Exception:
            raise pyautogui.PyAutoGUIException(
                "mss must be installed to use screenshot functions. Run: pip install mss Pillow"
            )

    with mss.mss() as sct:
        if region is not None:
            assert len(region) == 4, "region argument must be a tuple of four ints"
            left, top, width, height = [int(v) for v in region]
            capture_Area = {"left": left, "top": top, "width": width, "height": height}
        else:
            monitors = sct.monitors
            mon_idx = monitor if 0 <= monitor < len(monitors) else 1
            capture_Area = monitors[mon_idx]

        sct_img = sct.grab(capture_Area)
        im = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

    if imageFilename is not None:
        im.save(imageFilename)
    return im


def pixel(x, y):
    """
    Returns an ``RGB(red, green, blue)`` tuple of the screen pixel at ``(x, y)``.
    """
    im = screenshot(region=(int(x), int(y), 1, 1))
    r, g, b = im.getpixel((0, 0))[:3]
    return RGB(r, g, b)


def pixelMatchesColor(x, y, expectedRGBColor, tolerance=0):
    """
    Returns ``True`` if the pixel at ``(x, y)`` matches ``expectedRGBColor`` within ``tolerance``.
    """
    pix = pixel(x, y)
    if len(expectedRGBColor) == 3:
        r, g, b = pix[:3]
        exR, exG, exB = expectedRGBColor
        return (abs(r - exR) <= tolerance) and (abs(g - exG) <= tolerance) and (abs(b - exB) <= tolerance)
    elif len(expectedRGBColor) == 4:
        r, g, b = pix[:3]
        exR, exG, exB, _ = expectedRGBColor
        return (abs(r - exR) <= tolerance) and (abs(g - exG) <= tolerance) and (abs(b - exB) <= tolerance)
    else:
        raise ValueError(
            "expectedRGBColor must be a 3- or 4-integer tuple, but received %r" % (expectedRGBColor,)
        )


def _load_pil_image(img_or_path):
    """Load a PIL Image from a filename or return it if already an Image."""
    from PIL import Image

    if isinstance(img_or_path, Image.Image):
        return img_or_path.convert("RGB")
    if isinstance(img_or_path, str) and os.path.isfile(img_or_path):
        with Image.open(img_or_path) as im:
            return im.convert("RGB")
    return None


def _exact_locate_all_pil(needle_im, haystack_im, region=None):
    """
    Fast pure-Pillow exact byte search used when both needle and haystack are local images
    (e.g. unit tests calling locate('100x100blueimage.png', '100x100redimage.png')) or before VLM fallback.
    """
    offset_x, offset_y = 0, 0
    if region is not None:
        assert len(region) == 4, "region argument must be a tuple of four ints"
        offset_x, offset_y, rw, rh = [int(v) for v in region]
        haystack_im = haystack_im.crop((offset_x, offset_y, offset_x + rw, offset_y + rh))

    nw, nh = needle_im.size
    hw, hh = haystack_im.size
    if nw > hw or nh > hh or nw == 0 or nh == 0:
        return

    needle_bytes = needle_im.tobytes()
    haystack_bytes = haystack_im.tobytes()
    row_stride = hw * 3
    needle_row_stride = nw * 3
    first_row = needle_bytes[:needle_row_stride]

    start_pos = 0
    max_pos = (hh - nh) * row_stride + (hw - nw) * 3
    while start_pos <= max_pos:
        idx = haystack_bytes.find(first_row, start_pos)
        if idx == -1 or idx > max_pos:
            break
        if idx % 3 == 0:
            col = (idx % row_stride) // 3
            if col + nw <= hw:
                row = idx // row_stride
                match = True
                for r_offset in range(1, nh):
                    h_slice_start = idx + r_offset * row_stride
                    n_slice_start = r_offset * needle_row_stride
                    if haystack_bytes[h_slice_start : h_slice_start + needle_row_stride] != needle_bytes[
                        n_slice_start : n_slice_start + needle_row_stride
                    ]:
                        match = False
                        break
                if match:
                    yield Box(offset_x + col, offset_y + row, nw, nh)
        start_pos = idx + 3
