import os
import asyncio
from dotenv import load_dotenv
from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

load_dotenv()

MCP_SERVERS = {
    "file-service": {
        "url": "http://localhost:8000/mcp",
        "transport": "streamable_http",
    },
    "calculator-service": {
        "url": "http://localhost:8001/mcp",
        "transport": "streamable_http",
    },
}

# The file service scopes CSV files per session_id (so the web UI can give each
# visitor their own uploaded CSV). This terminal client is single-user, so it
# just pins every call to one fixed session.
CLI_SESSION_ID = "cli"


def _bind_session(file_tools: list) -> list:
    by_name = {t.name: t for t in file_tools}

    async def _read_csv() -> list[dict]:
        return await by_name["read_csv"].ainvoke({"session_id": CLI_SESSION_ID})

    async def _add_row(name: str, qty: int) -> dict:
        return await by_name["add_row"].ainvoke({"session_id": CLI_SESSION_ID, "name": name, "qty": qty})

    async def _update_qty(row_id: str, qty: int) -> str:
        return await by_name["update_qty"].ainvoke({"session_id": CLI_SESSION_ID, "row_id": row_id, "qty": qty})

    async def _delete_row(row_id: str) -> str:
        return await by_name["delete_row"].ainvoke({"session_id": CLI_SESSION_ID, "row_id": row_id})

    return [
        StructuredTool.from_function(coroutine=_read_csv, name="read_csv", description=by_name["read_csv"].description),
        StructuredTool.from_function(coroutine=_add_row, name="add_row", description=by_name["add_row"].description),
        StructuredTool.from_function(coroutine=_update_qty, name="update_qty", description=by_name["update_qty"].description),
        StructuredTool.from_function(coroutine=_delete_row, name="delete_row", description=by_name["delete_row"].description),
    ]


async def run_chat():
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("❌ Error: OPENAI_API_KEY is missing! Please check your .env file or environment variables.")
        return

    os.environ["OPENAI_API_KEY"] = api_key

    client = MultiServerMCPClient(MCP_SERVERS)

    try:
        calculator_tools = await client.get_tools(server_name="calculator-service")
        file_tools = await client.get_tools(server_name="file-service")
    except Exception as e:
        print(f"❌ Error getting tools from MCP servers: {e}")
        print("Please ensure that both file-service (port 8000) and calculator-service (port 8001) MCP servers are running.")
        return

    tools = calculator_tools + _bind_session(file_tools)
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    agent = create_agent(model, tools)

    while True:
        user_text = input("You: ").strip()

        result = await agent.ainvoke({"messages": [{"role": "user", "content": user_text}]})

        assistant_text = result["messages"][-1].content
        print(f"AI: {assistant_text}\n")


if __name__ == "__main__":
    asyncio.run(run_chat())
