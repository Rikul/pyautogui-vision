PyAutoGUI
=========

PyAutoGUI is a cross-platform GUI automation Python module for human beings and AI agents. Used to programmatically control the mouse & keyboard, capture fast screenshots via `mss`, and perform natural-language GUI tasks powered by Vision-Language Models (VLMs).

Works on **Windows**, **macOS**, **Linux**, and **WSL (Windows Subsystem for Linux)** (auto-detects WSL and bridges directly to the Windows host desktop).

Quickstart (`uv`)
=================

1. **Install dependencies and create the virtual environment with `uv`:**

```bash
uv sync
```

*(Optional)* To include the OpenAI SDK, MCP server, and LangChain agent extras:

```bash
uv sync --extra agent
```

2. **Configure a VLM (OpenAI, Ollama, vLLM, LM Studio, or OpenRouter) and run a task:**

```python
import pyautogui

# Connect to any OpenAI-compatible VLM endpoint (e.g., local Ollama / vLLM, or OpenAI)
pyautogui.configure_vlm(
    base_url="http://localhost:11434/v1",  # or "https://api.openai.com/v1"
    api_key="ollama",                      # or your OPENAI_API_KEY
    model="qwen2.5-vl",                    # or "gpt-4o"
)

# 1. Execute a compound natural-language instruction:
result = pyautogui.perform("type in my name 'Alice' in the first name field and hit enter")
print(result.summary)

# 2. Click or locate UI elements by natural language description:
pyautogui.click("the blue Submit button")
box = pyautogui.locateOnScreen("the search input box")

# 3. Inspect the current screen with a VLM:
answer = pyautogui.vlm_inspect("What error message is currently shown on the dialog?")
print(answer)
```

You can also configure the VLM via environment variables instead of calling `configure_vlm()`:
```bash
export PYAUTOGUI_VLM_BASE_URL="http://localhost:11434/v1"
export PYAUTOGUI_VLM_API_KEY="ollama"
export PYAUTOGUI_VLM_MODEL="qwen2.5-vl"
```

3. **Run commands or tests with `uv run`:**

```bash
uv run pytest
```

AI Agent Toolkit (`pyautogui.agent`)
====================================

PyAutoGUI includes built-in tool schemas (`TOOLS`) and adapters for AI agent frameworks:

```python
from pyautogui.agent import (
    TOOLS,
    execute_tool,
    capture_for_vlm,
    get_openai_tools,
    get_langchain_tools,
    create_mcp_server,
)

# Get OpenAI function-calling tool schemas:
tools = get_openai_tools()

# Execute a tool call returned by an LLM/VLM:
res = execute_tool("keyboard_type", {
    "target": "the first name field",
    "text": "Alice",
    "press_enter": True,
})

# Or expose PyAutoGUI as an MCP (Model Context Protocol) server:
mcp_server = create_mcp_server()
```

Dependencies
============

If you are installing PyAutoGUI using `uv sync` or `pip install pyautogui`:

* **Screen Capture**: Uses `mss` and `Pillow` for fast cross-platform screenshots (`pyscreeze` is no longer required).
* **Windows**: No extra OS dependencies.
* **WSL (Windows Subsystem for Linux)**: Auto-detected (`pyautogui.IS_WSL`); automatically controls the Windows host mouse, keyboard, and screen via Windows interop (`powershell.exe`). Set `PYAUTOGUI_WSL=0` to force native X11 mode inside WSLg.
* **macOS**: Uses `pyobjc-core` and `pyobjc-framework-quartz`.
* **Linux**: Uses `python3-Xlib` on X11.

Example Usage
=============

Keyboard and Mouse Control
--------------------------

The x, y coordinates used by PyAutoGUI has the 0, 0 origin coordinates in the top left corner of the screen. The x coordinates increase going to the right (just as in mathematics) but the y coordinates increase going down (the opposite of mathematics). On a screen that is 1920 x 1080 pixels in size, coordinates 0, 0 are for the top left while 1919, 1079 is for the bottom right.

Currently, PyAutoGUI only works on the primary monitor. PyAutoGUI isn't reliable for the screen of a second monitor (the mouse functions may or may not work on multi-monitor setups depending on your operating system and version).

All keyboard presses done by PyAutoGUI are sent to the window that currently has focus, as if you had pressed the physical keyboard key.

```python
    >>> import pyautogui
    >>> screenWidth, screenHeight = pyautogui.size() # Returns two integers, the width and height of the screen. (The primary monitor, in multi-monitor setups.)
    >>> currentMouseX, currentMouseY = pyautogui.position() # Returns two integers, the x and y of the mouse cursor's current position.
    >>> pyautogui.moveTo(100, 150) # Move the mouse to the x, y coordinates 100, 150.
    >>> pyautogui.click() # Click the mouse at its current location.
    >>> pyautogui.click(200, 220) # Click the mouse at the x, y coordinates 200, 220.
    >>> pyautogui.move(None, 10)  # Move mouse 10 pixels down, that is, move the mouse relative to its current position.
    >>> pyautogui.doubleClick() # Double click the mouse at the
    >>> pyautogui.moveTo(500, 500, duration=2, tween=pyautogui.easeInOutQuad) # Use tweening/easing function to move mouse over 2 seconds.
    >>> pyautogui.write('Hello world!', interval=0.25)  # Type with quarter-second pause in between each key.
    >>> pyautogui.press('esc') # Simulate pressing the Escape key.
    >>> pyautogui.keyDown('shift')
    >>> pyautogui.write(['left', 'left', 'left', 'left', 'left', 'left'])
    >>> pyautogui.keyUp('shift')
    >>> pyautogui.hotkey('ctrl', 'c')
```

Display Message Boxes
---------------------
```python
    >>> import pyautogui
    >>> pyautogui.alert('This is an alert box.')
    'OK'
    >>> pyautogui.confirm('Shall I proceed?')
    'Cancel'
    >>> pyautogui.confirm('Enter option.', buttons=['A', 'B', 'C'])
    'B'
    >>> pyautogui.prompt('What is your name?')
    'Al'
    >>> pyautogui.password('Enter password (text will be hidden)')
    'swordfish'
```

Screenshot Functions
--------------------

(PyAutoGUI uses Pillow for image-related features.)
```python
    >>> import pyautogui
    >>> im1 = pyautogui.screenshot()
    >>> im1.save('my_screenshot.png')
    >>> im2 = pyautogui.screenshot('my_screenshot2.png')
```
You can also locate where an image is on the screen:
```python
    >>> import pyautogui
    >>> button7location = pyautogui.locateOnScreen('button.png') # returns (left, top, width, height) of matching region
    >>> button7location
    (1416, 562, 50, 41)
    >>> buttonx, buttony = pyautogui.center(button7location)
    >>> buttonx, buttony
    (1441, 582)
    >>> pyautogui.click(buttonx, buttony)  # clicks the center of where the button was found
```
The locateCenterOnScreen() function returns the center of this match region:
```python
    >>> import pyautogui
    >>> buttonx, buttony = pyautogui.locateCenterOnScreen('button.png') # returns (x, y) of matching region
    >>> buttonx, buttony
    (1441, 582)
    >>> pyautogui.click(buttonx, buttony)  # clicks the center of where the button was found
```

How Does PyAutoGUI Work?
========================

The three major operating systems (Windows, macOS, and Linux) each have different ways to programmatically control the mouse and keyboard. This can often involve confusing, obscure, and deeply technical details. The job of PyAutoGUI is to hide all of this complexity behind a simple API.

* On Windows, PyAutoGUI accesses the Windows API (also called the WinAPI or win32 API) through the built-in `ctypes` module.
* On WSL, PyAutoGUI runs a persistent PowerShell Win32 P/Invoke bridge to control the Windows host desktop.
* On macOS, PyAutoGUI uses `pyobjc` (`Quartz` and `AppKit`) to access the Cocoa API.
* On Linux, PyAutoGUI uses the `Xlib` module to access the X11 or X Window System.


Support
-------

If you find this project helpful and would like to support its development, [consider donating to its creator on Patreon](https://www.patreon.com/AlSweigart).
