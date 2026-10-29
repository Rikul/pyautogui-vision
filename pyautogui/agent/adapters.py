# Optional AI Agent Framework adapters (OpenAI Agents / Function Calling, LangChain, and MCP).
# BSD license

import pyautogui
from pyautogui.agent.runner import perform
from pyautogui.agent.tools import TOOLS, execute_tool


def get_openai_tools():
    """
    Return the list of OpenAI Chat Completions / Responses API function tool schemas
    for PyAutoGUI inspection, mouse, and keyboard control.
    """
    return list(TOOLS)


def get_langchain_tools():
    """
    Return a list of LangChain ``StructuredTool`` objects wrapping PyAutoGUI's agent tools.
    Requires ``langchain-core`` to be installed.
    """
    try:
        from langchain_core.tools import StructuredTool
    except ImportError:
        raise pyautogui.PyAutoGUIException(
            "langchain-core must be installed to use get_langchain_tools(). Run: pip install langchain-core"
        )

    lc_tools = []
    for tool_def in TOOLS:
        fn_meta = tool_def["function"]
        name = fn_meta["name"]
        desc = fn_meta["description"]

        def _make_runner(tool_name):
            def _runner(**kwargs):
                return execute_tool(tool_name, kwargs)

            return _runner

        lc_tools.append(
            StructuredTool.from_function(
                func=_make_runner(name),
                name=name,
                description=desc,
            )
        )
    return lc_tools


def create_mcp_server(name="PyAutoGUI"):
    """
    Create and return a Model Context Protocol (MCP) ``FastMCP`` server exposing
    PyAutoGUI's screen inspection, mouse, keyboard, and ``perform`` tools.
    Requires the ``mcp`` package to be installed (``pip install mcp``).
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise pyautogui.PyAutoGUIException(
            "The 'mcp' package must be installed to create an MCP server. Run: pip install mcp"
        )

    mcp = FastMCP(name)

    @mcp.tool()
    def inspect_screen(draw_grid: bool = False) -> dict:
        """Capture an annotated screenshot of the desktop and return screen size, cursor position, and active window."""
        return execute_tool("inspect_screen", {"draw_grid": draw_grid})

    @mcp.tool()
    def locate_element(target: str) -> dict:
        """Use VLM visual grounding to find the bounding box and center coordinates of a UI element."""
        return execute_tool("locate_element", {"target": target})

    @mcp.tool()
    def mouse_click(
        x: int = None,
        y: int = None,
        target: str = None,
        button: str = "primary",
        clicks: int = 1,
        duration: float = 0.0,
    ) -> dict:
        """Click the mouse at (x, y) or on a natural-language target UI element."""
        return execute_tool(
            "mouse_click",
            {"x": x, "y": y, "target": target, "button": button, "clicks": clicks, "duration": duration},
        )

    @mcp.tool()
    def mouse_move(x: int = None, y: int = None, dx: int = None, dy: int = None, duration: float = 0.0) -> dict:
        """Move the mouse cursor to absolute (x, y) or relative (dx, dy)."""
        return execute_tool("mouse_move", {"x": x, "y": y, "dx": dx, "dy": dy, "duration": duration})

    @mcp.tool()
    def mouse_scroll(clicks: int, direction: str = "vertical", x: int = None, y: int = None) -> dict:
        """Scroll the mouse wheel vertically or horizontally."""
        return execute_tool("mouse_scroll", {"clicks": clicks, "direction": direction, "x": x, "y": y})

    @mcp.tool()
    def keyboard_type(
        text: str,
        x: int = None,
        y: int = None,
        target: str = None,
        press_enter: bool = False,
        clear_first: bool = False,
        interval: float = 0.0,
    ) -> dict:
        """Type text into the focused field (or click target/coordinates first) and optionally press Enter."""
        return execute_tool(
            "keyboard_type",
            {
                "text": text,
                "x": x,
                "y": y,
                "target": target,
                "press_enter": press_enter,
                "clear_first": clear_first,
                "interval": interval,
            },
        )

    @mcp.tool()
    def keyboard_press(keys: str, presses: int = 1) -> dict:
        """Press a special or character key (e.g. 'enter', 'tab', 'esc')."""
        return execute_tool("keyboard_press", {"keys": keys, "presses": presses})

    @mcp.tool()
    def keyboard_hotkey(keys: list) -> dict:
        """Press a keyboard shortcut combination (e.g. ['ctrl', 'c'])."""
        return execute_tool("keyboard_hotkey", {"keys": keys})

    @mcp.tool()
    def perform_instruction(instruction: str, max_steps: int = 10) -> dict:
        """Execute a compound natural-language GUI instruction via the VLM agent loop."""
        res = perform(instruction, max_steps=max_steps)
        return {"success": res.success, "summary": res.summary, "steps": res.steps}

    return mcp
