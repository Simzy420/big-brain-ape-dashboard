#!/usr/bin/env python3.11
"""
Big Brain Ape — Chat Server
Receives messages from the to-do app chat box, stores them,
and serves responses from the agent.
"""
import json, os, time, uuid
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

MESSAGES_FILE = os.path.expanduser("~/.hermes/bba-chat/messages.json")
os.makedirs(os.path.dirname(MESSAGES_FILE), exist_ok=True)

app = FastAPI(title="BBA Chat")

# Allow any origin (the web app is on GitHub Pages)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_messages():
    try:
        with open(MESSAGES_FILE) as f:
            return json.load(f)
    except:
        return []

def save_messages(msgs):
    with open(MESSAGES_FILE, "w") as f:
        json.dump(msgs, f, indent=2)

@app.get("/")
async def health():
    return {"status": "ok", "service": "bba-chat"}

@app.get("/messages")
async def get_messages(since: int = 0):
    """Get all messages since a timestamp. Web app polls this."""
    msgs = load_messages()
    recent = [m for m in msgs if m.get("ts", 0) > since]
    return {"messages": recent}

@app.post("/send")
async def send_message(request: Request):
    """Receive a message from the user via the web chat box."""
    body = await request.json()
    text = body.get("text", "").strip()
    if not text:
        return JSONResponse({"error": "empty message"}, status_code=400)
    
    msgs = load_messages()
    msg = {
        "id": str(uuid.uuid4()),
        "ts": int(time.time()),
        "role": "user",
        "text": text
    }
    msgs.append(msg)
    # Keep last 200 messages
    msgs = msgs[-200:]
    save_messages(msgs)
    
    return {"status": "ok", "message": msg}

@app.post("/respond")
async def post_response(request: Request):
    """Agent posts a response. Protected by a simple shared secret."""
    body = await request.json()
    secret = body.get("secret", "")
    expected = os.environ.get("BBA_CHAT_SECRET", "bba-chat-2026")
    
    if secret != expected:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    
    text = body.get("text", "").strip()
    if not text:
        return JSONResponse({"error": "empty response"}, status_code=400)
    
    msgs = load_messages()
    msg = {
        "id": str(uuid.uuid4()),
        "ts": int(time.time()),
        "role": "agent",
        "text": text
    }
    msgs.append(msg)
    msgs = msgs[-200:]
    save_messages(msgs)
    
    return {"status": "ok", "message": msg}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
