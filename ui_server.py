import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

load_dotenv()

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ Error: OPENAI_API_KEY is missing!")
        yield
        return

    os.environ["OPENAI_API_KEY"] = api_key
    
    try:
        client = MultiServerMCPClient(MCP_SERVERS)
        tools = await client.get_tools()
        model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        agent = create_agent(model, tools)
    except Exception as e:
        print(f"❌ Error initializing agent: {e}")
        print("Please ensure that both file-service and calculator-service MCP servers are running.")
    
    yield

app = FastAPI(lifespan=lifespan)

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

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

agent = None
chat_history = []

# The startup logic has been moved to the lifespan context manager above.

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    global agent, chat_history
    if not agent:
        return ChatResponse(response="Error: Agent not initialized. Check OPENAI_API_KEY and ensure MCP servers are running.")
    
    # Append new user message
    chat_history.append({"role": "user", "content": req.message})
    
    try:
        # We pass the full history to the agent so it has context of previous messages
        result = await agent.ainvoke({"messages": chat_history})
        assistant_text = result["messages"][-1].content
        
        # Append AI response to history
        chat_history.append({"role": "assistant", "content": assistant_text})
        return ChatResponse(response=assistant_text)
    except Exception as e:
        return ChatResponse(response=f"Error communicating with AI: {str(e)}")

@app.get("/api/clear")
async def clear_chat():
    global chat_history
    chat_history = []
    return {"status": "ok"}

# Create ui directory if it doesn't exist
os.makedirs("ui", exist_ok=True)

# Mount static files
app.mount("/ui", StaticFiles(directory="ui"), name="ui")

@app.get("/")
async def root():
    return FileResponse("ui/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ui_server:app", host="0.0.0.0", port=8082, reload=True)
