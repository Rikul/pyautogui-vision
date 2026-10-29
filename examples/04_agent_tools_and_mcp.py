"""
Example 4: Using PyAutoGUI's AI Agent Toolkit (OpenAI Function Calling, LangChain, and MCP Server).

Run tool inspection demo:
    uv run python examples/04_agent_tools_and_mcp.py

Or launch PyAutoGUI as a Model Context Protocol (MCP) server over stdio:
    uv run --extra agent python examples/04_agent_tools_and_mcp.py --mcp
"""

import json
import sys
from pyautogui.agent import (
    create_mcp_server,
    execute_tool,
    get_openai_tools,
)


def demo_tools():
    tools = get_openai_tools()
    print(f"Available PyAutoGUI Agent Tools ({len(tools)}):")
    for t in tools:
        fn = t["function"]
        print(f"  - {fn['name']}: {fn['description']}")

    # Execute a safe read-only tool call (inspect_screen)
    print("\nExecuting 'inspect_screen' tool...")
    res = execute_tool("inspect_screen", {"draw_grid": False})
    print("Screen State:", json.dumps(res["state"], indent=2))
    print(f"Screenshot Base64 Length: {len(res['base64_png'])} chars")


def main():
    if "--mcp" in sys.argv:
        mcp = create_mcp_server("PyAutoGUI-Desktop-Agent")
        mcp.run()
    else:
        demo_tools()


if __name__ == "__main__":
    main()
