# PyAutoGUI Examples

These examples show how to use PyAutoGUI's `mss` screen capture, VLM visual grounding, `pyautogui.perform()`, and the `pyautogui.agent` toolkit.

## Setup

1. Sync the environment with `uv`:
   ```bash
   uv sync
   ```
2. Copy `.env.example` to `.env` (or export the environment variables) and configure your VLM endpoint (OpenAI, Ollama, vLLM, LM Studio, or OpenRouter):
   ```bash
   cp .env.example .env
   ```

## Running the Examples

* **[`01_basic_mouse_keyboard_mss.py`](./01_basic_mouse_keyboard_mss.py)** — Fast `mss` screenshots, pixel color checks, cursor inspection, and mouse/keyboard control (works natively on Windows, macOS, Linux, and WSL):
  ```bash
  uv run python examples/01_basic_mouse_keyboard_mss.py
  ```

* **[`02_vlm_locate_and_inspect.py`](./02_vlm_locate_and_inspect.py)** — Semantic UI locating (`locateOnScreen`, `vlm_locate_center`, `click("target")`) and screen Q&A (`vlm_inspect`):
  ```bash
  uv run python examples/02_vlm_locate_and_inspect.py
  ```

* **[`03_perform_natural_language.py`](./03_perform_natural_language.py)** — Executing compound natural-language instructions with `pyautogui.perform()` (e.g., *"type in my name in the first name field and hit enter"*):
  ```bash
  uv run python examples/03_perform_natural_language.py
  ```

* **[`04_agent_tools_and_mcp.py`](./04_agent_tools_and_mcp.py)** — Using `pyautogui.agent` tool schemas (`get_openai_tools()`, `execute_tool()`, `capture_for_vlm()`) or starting the PyAutoGUI MCP server:
  ```bash
  uv run python examples/04_agent_tools_and_mcp.py
  # Or run as an MCP server over stdio:
  uv run python examples/04_agent_tools_and_mcp.py --mcp
  ```
