# PyAutoGUI-vision

Cross-platform GUI automation for Python and AI agents. Control the mouse and keyboard, capture fast screenshots via `mss`, and execute natural-language GUI tasks powered by Vision-Language Models (VLMs).

Works natively on **Windows**, **macOS**, **Linux**, and **WSL** (auto-detects WSL and bridges directly to the Windows host desktop).

## Quickstart

1. **Install with `uv`:**

```bash
uv sync
# Optional: include OpenAI SDK, MCP server, and LangChain extras
uv sync --extra agent
```

2. **Configure your VLM** (copy `.env.example` to `.env` or call `configure_vlm()`):

```bash
cp .env.example .env
```

3. **Run natural-language or classic GUI automation:**

```python
import pyautogui

# Connect to any OpenAI-compatible VLM (Ollama, vLLM, LM Studio, OpenAI, OpenRouter)
pyautogui.configure_vlm(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
    model="qwen2.5-vl",
)

# Execute compound natural-language instructions
result = pyautogui.perform("type in my name 'Alice' in the first name field and hit enter")
print(result.summary)

# Click or locate UI elements by description
pyautogui.click("the blue Submit button")
box = pyautogui.locateOnScreen("the search input box")

# Ask questions about the current screen
print(pyautogui.vlm_inspect("What application is currently focused?"))
```

## Classic Mouse, Keyboard & `mss` Screenshots

```python
import pyautogui

width, height = pyautogui.size()
x, y = pyautogui.position()

pyautogui.moveTo(100, 150)
pyautogui.click(200, 220)
pyautogui.write("Hello world!", interval=0.05)
pyautogui.press("enter")
pyautogui.hotkey("ctrl", "c")

# Fast screen capture via mss
im = pyautogui.screenshot("screenshot.png")
rgb = pyautogui.pixel(x, y)
```

## AI Agent Toolkit (`pyautogui.agent`)

Use built-in OpenAI function-calling schemas, LangChain tools, or run as an MCP server:

```python
from pyautogui.agent import get_openai_tools, execute_tool, create_mcp_server

tools = get_openai_tools()
res = execute_tool("keyboard_type", {
    "target": "the first name field",
    "text": "Alice",
    "press_enter": True,
})

# Or expose as a Model Context Protocol (MCP) server:
mcp = create_mcp_server()
```

See the [`examples/`](./examples/) directory for runnable scripts:
```bash
uv run python examples/01_basic_mouse_keyboard_mss.py
uv run python examples/02_vlm_locate_and_inspect.py
uv run python examples/03_perform_natural_language.py
uv run python examples/04_agent_tools_and_mcp.py
```
