# OpenAI-compatible Vision-Language Model (VLM) client and visual grounding for PyAutoGUI.
# Supports OpenAI, Ollama, vLLM, LM Studio, OpenRouter, and any OpenAI-compatible API.
# BSD license

import base64
import io
import json
import os
import re
import urllib.error
import urllib.request

import pyautogui
from pyautogui._screen import Box, _exact_locate_all_pil, _load_pil_image, center, screenshot


class _VLMConfig(object):
    def __init__(self):
        self.base_url = os.environ.get("PYAUTOGUI_VLM_BASE_URL", "https://api.openai.com/v1")
        self.api_key = os.environ.get("PYAUTOGUI_VLM_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        self.model = os.environ.get("PYAUTOGUI_VLM_MODEL", "gpt-4o")
        self.timeout = float(os.environ.get("PYAUTOGUI_VLM_TIMEOUT", "60.0"))
        self.coord_scale = os.environ.get("PYAUTOGUI_VLM_COORD_SCALE", "pixel")  # "pixel" or "normalized_1000"
        self.custom_client = None


_config = _VLMConfig()


def configure_vlm(
    base_url=None,
    api_key=None,
    model=None,
    timeout=None,
    coord_scale=None,
    client=None,
):
    """
    Configure the OpenAI-compatible VLM connection used by PyAutoGUI for visual grounding and ``perform()``.

    Args:
      base_url (str, optional): API base URL (e.g. ``"https://api.openai.com/v1"``, ``"http://localhost:11434/v1"``).
      api_key (str, optional): API key (or ``"ollama"`` / ``"local"`` for local servers).
      model (str, optional): VLM model name (e.g. ``"gpt-4o"``, ``"qwen2.5-vl"``, ``"llama3.2-vision"``).
      timeout (float, optional): Request timeout in seconds.
      coord_scale (str, optional): Coordinate system returned by the model: ``"pixel"`` (default) or ``"normalized_1000"``.
      client (object, optional): Optional pre-configured ``openai.OpenAI`` client instance.
    """
    if base_url is not None:
        _config.base_url = base_url.rstrip("/")
    if api_key is not None:
        _config.api_key = api_key
    if model is not None:
        _config.model = model
    if timeout is not None:
        _config.timeout = float(timeout)
    if coord_scale is not None:
        _config.coord_scale = coord_scale
    if client is not None:
        _config.custom_client = client


def get_vlm_config():
    """Return a dictionary of the current VLM configuration."""
    return {
        "base_url": _config.base_url,
        "api_key": _config.api_key,
        "model": _config.model,
        "timeout": _config.timeout,
        "coord_scale": _config.coord_scale,
    }


def is_vlm_configured():
    """Return True if a VLM client, API key, or custom local base_url has been configured."""
    if _config.custom_client is not None:
        return True
    if _config.api_key or os.environ.get("PYAUTOGUI_VLM_API_KEY") or os.environ.get("OPENAI_API_KEY"):
        return True
    if os.environ.get("PYAUTOGUI_VLM_BASE_URL"):
        return True
    if _config.base_url != "https://api.openai.com/v1":
        return True
    return False


def encode_image_base64(pil_image, format="PNG"):
    """Encode a PIL.Image.Image to a base64 ASCII string."""
    buf = io.BytesIO()
    pil_image.save(buf, format=format)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def chat_completion(messages, tools=None, tool_choice=None, temperature=0.0, response_format=None):
    """
    Send a chat completion request to the configured OpenAI-compatible VLM endpoint.
    Uses a custom ``openai.OpenAI`` client if provided, the ``openai`` package if installed,
    or falls back to standard library ``urllib.request``.

    Returns a normalized dict matching the OpenAI Chat Completion response structure:
    ``{"choices": [{"message": {"role": "assistant", "content": "...", "tool_calls": [...]}}]}``
    """
    base_url = (os.environ.get("PYAUTOGUI_VLM_BASE_URL") or _config.base_url).rstrip("/")
    api_key = _config.api_key or os.environ.get("PYAUTOGUI_VLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or "local"
    model = os.environ.get("PYAUTOGUI_VLM_MODEL") or _config.model

    if _config.custom_client is not None:
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
        if response_format:
            kwargs["response_format"] = response_format
        resp = _config.custom_client.chat.completions.create(**kwargs)
        if isinstance(resp, dict):
            return resp
        if hasattr(resp, "model_dump"):
            return resp.model_dump()
        return json.loads(resp.json())

    # HTTP request via standard library urllib (zero external dependency required, works with all OpenAI-compatible servers)
    url = base_url + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools
    if tool_choice:
        payload["tool_choice"] = tool_choice
    if response_format:
        payload["response_format"] = response_format

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer %s" % api_key,
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_config.timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise pyautogui.PyAutoGUIException(
            "VLM API HTTP %d error from %s: %s" % (exc.code, url, err_body or exc.reason)
        )
    except urllib.error.URLError as exc:
        raise pyautogui.PyAutoGUIException("Failed to connect to VLM API at %s: %s" % (url, exc.reason))


def _extract_json_from_text(text):
    """Extract a JSON object or array from model output (stripping markdown code fences if present)."""
    if not text:
        return None
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    # Try locating first '{' or '['
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        s_idx = text.find(start_char)
        e_idx = text.rfind(end_char)
        if s_idx != -1 and e_idx != -1 and e_idx > s_idx:
            try:
                return json.loads(text[s_idx : e_idx + 1])
            except Exception:
                pass
    return None


def _convert_box_to_pixels(box_dict, img_width, img_height, offset_x=0, offset_y=0):
    """Convert a VLM bounding box dict into a PyAutoGUI Box(left, top, width, height) in screen pixels."""
    if not isinstance(box_dict, dict):
        return None

    if "bbox_2d" in box_dict and isinstance(box_dict["bbox_2d"], (list, tuple)) and len(box_dict["bbox_2d"]) == 4:
        x1, y1, x2, y2 = [float(v) for v in box_dict["bbox_2d"]]
        left, top, width, height = x1, y1, x2 - x1, y2 - y1
    elif all(k in box_dict for k in ("left", "top", "width", "height")):
        left = float(box_dict["left"])
        top = float(box_dict["top"])
        width = float(box_dict["width"])
        height = float(box_dict["height"])
    elif all(k in box_dict for k in ("x", "y", "width", "height")):
        left = float(box_dict["x"])
        top = float(box_dict["y"])
        width = float(box_dict["width"])
        height = float(box_dict["height"])
    elif all(k in box_dict for k in ("x1", "y1", "x2", "y2")):
        x1, y1, x2, y2 = float(box_dict["x1"]), float(box_dict["y1"]), float(box_dict["x2"]), float(box_dict["y2"])
        left, top, width, height = x1, y1, x2 - x1, y2 - y1
    elif all(k in box_dict for k in ("x", "y")):
        cx, cy = float(box_dict["x"]), float(box_dict["y"])
        left, top, width, height = cx - 5, cy - 5, 10, 10
    else:
        return None

    scale_mode = box_dict.get("coord_scale") or _config.coord_scale
    if scale_mode == "normalized_1000":
        left = (left / 1000.0) * img_width
        top = (top / 1000.0) * img_height
        width = (width / 1000.0) * img_width
        height = (height / 1000.0) * img_height

    return Box(
        int(round(offset_x + left)),
        int(round(offset_y + top)),
        max(1, int(round(width))),
        max(1, int(round(height))),
    )


def vlm_locate_all(target, haystack_image=None, region=None):
    """
    Use the configured Vision-Language Model (VLM) to locate all occurrences of ``target``
    (a natural-language description or a reference image/filename) inside ``haystack_image``
    (or a fresh screenshot if ``None``).

    Returns a list of ``Box(left, top, width, height)`` tuples.
    """
    offset_x, offset_y = 0, 0
    if haystack_image is None:
        haystack_pil = screenshot(region=region)
        if region is not None:
            offset_x, offset_y = int(region[0]), int(region[1])
    else:
        haystack_pil = _load_pil_image(haystack_image)
        if haystack_pil is None:
            raise pyautogui.PyAutoGUIException("Could not load haystack image: %r" % (haystack_image,))
        if region is not None:
            offset_x, offset_y, rw, rh = [int(v) for v in region]
            haystack_pil = haystack_pil.crop((offset_x, offset_y, offset_x + rw, offset_y + rh))

    img_w, img_h = haystack_pil.size
    haystack_b64 = encode_image_base64(haystack_pil)

    needle_pil = _load_pil_image(target)
    content_parts = []

    if needle_pil is not None:
        needle_b64 = encode_image_base64(needle_pil)
        prompt_text = (
            "Locate all occurrences of the first image (the template/needle) inside the second image "
            "(the screen/haystack, dimensions %dx%d pixels). "
            'Return ONLY valid JSON in the format: {"found": true, "boxes": [{"left": <int>, "top": <int>, "width": <int>, "height": <int>}]} '
            'in pixel coordinates, or {"found": false, "boxes": []} if not present.' % (img_w, img_h)
        )
        content_parts.append({"type": "text", "text": prompt_text})
        content_parts.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + needle_b64}})
        content_parts.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + haystack_b64}})
    else:
        prompt_text = (
            "Locate all UI elements matching the description %r in this screenshot (dimensions %dx%d pixels). "
            'Return ONLY valid JSON in the format: {"found": true, "boxes": [{"left": <int>, "top": <int>, "width": <int>, "height": <int>}]} '
            'in pixel coordinates, or {"found": false, "boxes": []} if not present.' % (str(target), img_w, img_h)
        )
        content_parts.append({"type": "text", "text": prompt_text})
        content_parts.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + haystack_b64}})

    messages = [
        {
            "role": "system",
            "content": "You are a precise GUI visual grounding model. Always respond with valid JSON containing exact pixel bounding boxes.",
        },
        {"role": "user", "content": content_parts},
    ]

    resp = chat_completion(messages, temperature=0.0)
    msg_content = resp["choices"][0]["message"].get("content", "")
    parsed = _extract_json_from_text(msg_content)
    if not parsed:
        return []

    boxes_raw = []
    if isinstance(parsed, dict):
        if parsed.get("found") is False:
            return []
        if "boxes" in parsed and isinstance(parsed["boxes"], list):
            boxes_raw = parsed["boxes"]
        elif any(k in parsed for k in ("left", "x", "x1", "bbox_2d")):
            boxes_raw = [parsed]
    elif isinstance(parsed, list):
        boxes_raw = parsed

    results = []
    for item in boxes_raw:
        box = _convert_box_to_pixels(item, img_w, img_h, offset_x=offset_x, offset_y=offset_y)
        if box is not None:
            results.append(box)
    return results


def vlm_locate(target, haystack_image=None, region=None):
    """
    Locate the first occurrence of ``target`` using the VLM and return ``Box(left, top, width, height)``.
    Raises ``pyautogui.ImageNotFoundException`` if ``USE_IMAGE_NOT_FOUND_EXCEPTION`` is True, else returns ``None``.
    """
    boxes = vlm_locate_all(target, haystack_image=haystack_image, region=region)
    if boxes:
        return boxes[0]
    if pyautogui._screen.USE_IMAGE_NOT_FOUND_EXCEPTION:
        raise pyautogui.ImageNotFoundException("Could not locate %r via VLM." % (target,))
    return None


def vlm_locate_center(target, haystack_image=None, region=None):
    """Locate ``target`` via the VLM and return its ``Point(x, y)`` center."""
    box = vlm_locate(target, haystack_image=haystack_image, region=region)
    if box is None:
        return None
    return center(box)


def vlm_inspect(prompt="Describe the current screen state and active UI elements.", region=None, screenshot_img=None):
    """
    Capture the screen (or use ``screenshot_img``) and ask the VLM a question about it.
    Returns the VLM's text response.
    """
    im = _load_pil_image(screenshot_img) if screenshot_img is not None else screenshot(region=region)
    b64 = encode_image_base64(im)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}},
            ],
        }
    ]
    resp = chat_completion(messages, temperature=0.0)
    return resp["choices"][0]["message"].get("content", "")


def locateAll(needleImage, haystackImage, grayscale=None, limit=None, region=None, step=1, confidence=None):
    """
    Locate all occurrences of ``needleImage`` (either an image/filename or a VLM natural-language prompt)
    inside ``haystackImage``.
    Uses a fast exact-pixel check first if ``needleImage`` is a valid image file/PIL.Image, and delegates
    to ``vlm_locate_all`` if ``needleImage`` is a natural-language query or if VLM is configured.
    """
    needle_pil = _load_pil_image(needleImage)
    haystack_pil = _load_pil_image(haystackImage)

    if needle_pil is not None and haystack_pil is not None:
        matches = list(_exact_locate_all_pil(needle_pil, haystack_pil, region=region))
        if matches or not is_vlm_configured():
            if limit is not None:
                matches = matches[:limit]
            for m in matches:
                yield m
            return

    if is_vlm_configured() or needle_pil is None:
        matches = vlm_locate_all(needleImage, haystack_image=haystack_pil or haystackImage, region=region)
        if limit is not None:
            matches = matches[:limit]
        for m in matches:
            yield m


def locate(needleImage, haystackImage, **kwargs):
    """
    Locate the first occurrence of ``needleImage`` (image or VLM prompt) in ``haystackImage``.
    """
    matches = list(locateAll(needleImage, haystackImage, limit=1, **kwargs))
    if matches:
        return matches[0]
    if pyautogui._screen.USE_IMAGE_NOT_FOUND_EXCEPTION:
        raise pyautogui.ImageNotFoundException("Could not locate %r" % (needleImage,))
    return None


def locateAllOnScreen(image, minSearchTime=0, **kwargs):
    """
    Capture the screen via ``mss`` and yield all ``Box(left, top, width, height)`` matches for ``image``
    (which can be a natural-language VLM description or an image file).
    """
    region = kwargs.pop("region", None)
    screen_im = screenshot(region=region)
    offset_x, offset_y = (int(region[0]), int(region[1])) if region is not None else (0, 0)
    for box in locateAll(image, screen_im, **kwargs):
        yield Box(box.left + offset_x, box.top + offset_y, box.width, box.height)


def locateOnScreen(image, minSearchTime=0, **kwargs):
    """
    Locate ``image`` (natural-language description or image file) on screen.
    Returns ``Box(left, top, width, height)`` or raises ``ImageNotFoundException`` / returns ``None``.
    """
    matches = list(locateAllOnScreen(image, minSearchTime=minSearchTime, limit=1, **kwargs))
    if matches:
        return matches[0]
    if pyautogui._screen.USE_IMAGE_NOT_FOUND_EXCEPTION:
        raise pyautogui.ImageNotFoundException("Could not locate %r on screen." % (image,))
    return None


def locateCenterOnScreen(image, **kwargs):
    """
    Locate ``image`` (natural-language description or image file) on screen and return its center ``Point(x, y)``.
    """
    coords = locateOnScreen(image, **kwargs)
    if coords is None:
        return None
    return center(coords)


def locateOnWindow(image, title, **kwargs):
    """
    Locate ``image`` (natural-language description or image file) inside the window matching ``title``.
    """
    if hasattr(pyautogui, "getWindowsWithTitle"):
        windows = pyautogui.getWindowsWithTitle(title)
        if not windows:
            raise pyautogui.PyAutoGUIException('Could not find a window with "%s" in the title' % (title,))
        win = windows[0]
        return locateOnScreen(image, region=(win.left, win.top, win.width, win.height), **kwargs)
    raise pyautogui.PyAutoGUIException("locateOnWindow() requires pygetwindow support on this platform.")
