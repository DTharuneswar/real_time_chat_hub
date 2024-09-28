from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles  
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import asyncio
import json
import logging
import csv
import os
from datetime import datetime

app = FastAPI(title="RealTime Chat Hub", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

app.mount("/static", StaticFiles(directory="static"), name="static")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Message(BaseModel):
    client_id: str
    content: str
    timestamp: str

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.message_history: List[Message] = []
        self.csv_file_path = "message_history.csv"
        # Create CSV file and write header if it doesn't exist
        if not os.path.exists(self.csv_file_path):
            with open(self.csv_file_path, mode='w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["sender", "message", "time"])

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        await self.broadcast(f"System: {client_id} has joined the chat.")

    def disconnect(self, client_id: str):
        del self.active_connections[client_id]

    async def send_personal_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)

    def add_to_history(self, message: Message):
        self.message_history.append(message)
        self.append_to_csv(message)
        if len(self.message_history) > 100:  
            self.message_history.pop(0)

    def append_to_csv(self, message: Message):
        with open(self.csv_file_path, mode='a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([message.client_id, message.content, message.timestamp])

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def get():
    with open("static/wbindex.html", "r") as file:
        html_content = file.read()
    return HTMLResponse(content=html_content, status_code=200)

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    try:
        for msg in manager.message_history:
            await manager.send_personal_message(json.dumps(msg.dict()), client_id)
        
        while True:
            data = await websocket.receive_text()
            message = Message(
                client_id=client_id,
                content=data,
                timestamp=datetime.now().isoformat()
            )
            manager.add_to_history(message)
            await manager.broadcast(json.dumps(message.dict()))
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        await manager.broadcast(f"System: {client_id} has left the chat")
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {str(e)}")

@app.get("/history", response_model=List[Message])
async def get_message_history():
    return manager.message_history

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return {"detail": str(exc.detail), "status_code": exc.status_code}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
