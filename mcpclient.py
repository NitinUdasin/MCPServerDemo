import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import ToolMessage
import json
import sys

load_dotenv()

async def main():
    connections = {
        "Financial Data Provider": {
            "transport": "stdio",
            "command": "C:\\Users\\nitin\\.local\\bin\\uv.exe",
            "args": [
                "run",
                "fastmcp",
                "run",
                "C:\\WorkSpace\\POC\\MCPServerDemo\\DataprovidersMCPServer.py"
            ]
        }
    }
    
    client = MultiServerMCPClient(connections)
    tools = await client.get_tools()
    print(f"Available tools: {tools}")

    llm = ChatOpenAI(model="gpt-4")
    llm_with_tools = llm.bind_tools(tools)

    named_tools = {}
    for tool in tools:
        named_tools[tool.name] = tool

    prompt = "What is BAJFINANCE StockPE"
    response = await llm_with_tools.ainvoke(prompt)

    if not getattr(response, "tool_calls", None):
        print("\nLLM Reply:", response.content)
        return

    tool_messages = []
    for tc in response.tool_calls:
        selected_tool = tc["name"]
        selected_tool_args = tc.get("args") or {}
        selected_tool_id = tc["id"]

        result = await named_tools[selected_tool].ainvoke(selected_tool_args)
        tool_messages.append(ToolMessage(tool_call_id=selected_tool_id, content=json.dumps(result)))


    final_response = await llm_with_tools.ainvoke([prompt, response, *tool_messages])
    print(f"Final response: {final_response.content}")

if __name__ == '__main__':
    asyncio.run(main())
