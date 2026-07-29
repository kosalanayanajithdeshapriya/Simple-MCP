import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

load_dotenv()

from contextlib import asynccontextmanager

SESSION_COOKIE = "sid"
DATA_DIR = Path("data")

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

model = None
calculator_tools: list = []
file_tools: list = []
agents_by_session: dict[str, object] = {}
chat_history_by_session: dict[str, list] = {}


def _session_scoped_file_tools(session_id: str) -> list:
    """Wrap the shared file-service MCP tools so each session's calls are pinned
    to its own session_id. The LLM never sees or supplies session_id itself -
    it's injected here, so sessions can't read or overwrite each other's CSVs."""
    by_name = {t.name: t for t in file_tools}

    async def _read_csv() -> list[dict]:
        return await by_name["read_csv"].ainvoke({"session_id": session_id})

    async def _add_row(name: str, qty: int) -> dict:
        return await by_name["add_row"].ainvoke({"session_id": session_id, "name": name, "qty": qty})

    async def _update_qty(row_id: str, qty: int) -> str:
        return await by_name["update_qty"].ainvoke({"session_id": session_id, "row_id": row_id, "qty": qty})

    async def _delete_row(row_id: str) -> str:
        return await by_name["delete_row"].ainvoke({"session_id": session_id, "row_id": row_id})

    return [
        StructuredTool.from_function(coroutine=_read_csv, name="read_csv", description=by_name["read_csv"].description),
        StructuredTool.from_function(coroutine=_add_row, name="add_row", description=by_name["add_row"].description),
        StructuredTool.from_function(coroutine=_update_qty, name="update_qty", description=by_name["update_qty"].description),
        StructuredTool.from_function(coroutine=_delete_row, name="delete_row", description=by_name["delete_row"].description),
    ]


def get_agent(session_id: str):
    if session_id not in agents_by_session:
        tools = calculator_tools + _session_scoped_file_tools(session_id)
        agents_by_session[session_id] = create_agent(model, tools)
    return agents_by_session[session_id]


def get_session_id(request: Request, response: Response) -> str:
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        sid = uuid.uuid4().hex
        response.set_cookie(SESSION_COOKIE, sid, httponly=True, samesite="lax", max_age=60 * 60 * 24)
    return sid


def _session_csv_path(session_id: str) -> Path:
    safe_id = "".join(c for c in session_id if c.isalnum() or c in "_-") or "default"
    return DATA_DIR / f"{safe_id}.csv"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, calculator_tools, file_tools
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ Error: OPENAI_API_KEY is missing!")
        yield
        return

    os.environ["OPENAI_API_KEY"] = api_key

    try:
        client = MultiServerMCPClient(MCP_SERVERS)
        calculator_tools = await client.get_tools(server_name="calculator-service")
        file_tools = await client.get_tools(server_name="file-service")
        model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    except Exception as e:
        print(f"❌ Error initializing agent: {e}")
        print("Please ensure that both file-service and calculator-service MCP servers are running.")

    yield


app = FastAPI(lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request, response: Response):
    if model is None:
        return ChatResponse(response="Error: Agent not initialized. Check OPENAI_API_KEY and ensure MCP servers are running.")

    session_id = get_session_id(request, response)
    agent = get_agent(session_id)
    history = chat_history_by_session.setdefault(session_id, [])

    history.append({"role": "user", "content": req.message})

    try:
        result = await agent.ainvoke({"messages": history})
        assistant_text = result["messages"][-1].content
        history.append({"role": "assistant", "content": assistant_text})
        return ChatResponse(response=assistant_text)
    except Exception as e:
        return ChatResponse(response=f"Error communicating with AI: {str(e)}")


@app.get("/api/clear")
async def clear_chat(request: Request, response: Response):
    session_id = get_session_id(request, response)
    chat_history_by_session[session_id] = []
    return {"status": "ok"}


@app.post("/api/upload")
async def upload_csv(request: Request, response: Response, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported.")

    session_id = get_session_id(request, response)
    DATA_DIR.mkdir(exist_ok=True)
    contents = await file.read()
    _session_csv_path(session_id).write_bytes(contents)
    return {"status": "ok", "filename": file.filename}


# Create ui directory if it doesn't exist
os.makedirs("ui", exist_ok=True)

# Mount static files
app.mount("/ui", StaticFiles(directory="ui"), name="ui")

@app.get("/")
async def root():
    return FileResponse("ui/index.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8082))
    reload = os.getenv("ENV", "development") != "production"
    uvicorn.run("ui_server:app", host="0.0.0.0", port=port, reload=reload)
