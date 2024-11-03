from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict
import json
import logging
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import os

# Create static directory if it doesn't exist
os.makedirs("static", exist_ok=True)

app = FastAPI(title="RealTime Chat Hub", version="1.0.0")

# Mount the static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Message(BaseModel):
    client_id: str
    content: str
    timestamp: str

# MongoDB configuration
MONGO_DETAILS = "mongodb://localhost:27017"
client = AsyncIOMotorClient(MONGO_DETAILS)
db = client.chat_db
messages_collection = db.messages

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        await self.broadcast(
            json.dumps({
                "client_id": "System",
                "content": f"{client_id} has joined the chat",
                "timestamp": datetime.now().isoformat()
            })
        )

    def disconnect(self, client_id: str):
        del self.active_connections[client_id]

    async def send_personal_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)

    async def add_to_history(self, message: Message):
        await messages_collection.insert_one(message.dict())

    async def get_message_history(self) -> List[Message]:
        messages = await messages_collection.find().sort("timestamp", -1).to_list(100)
        return [Message(**message) for message in messages]

manager = ConnectionManager()

# Complete HTML template with all styles and content
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NightOwl Chat</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: Georgia, serif;
            background: url('/static/bg.png') no-repeat center center fixed;
            background-size: cover;
            color: #e0e0e0;
        }
        .overlay {
            background-color: rgba(18, 18, 18, 0.8);
            min-height: 100vh;
            padding: 20px;
        }
        .card {
            background-color: #1e1e1e;
            border: none;
            border-radius: 15px;
        }
        .btn-orange {
            background-color: #ff6a00;
            border-color: #ff6a00;
            color: white;
            border-radius: 25px;
            padding: 10px 20px;
            transition: all 0.3s ease;
        }
        .btn-orange:hover {
            background-color: #ff8c00;
            border-color: #ff8c00;
            color: white;
        }
        .form-control {
            background-color: #2a2a2a;
            border: none;
            color: #e0e0e0;
            border-radius: 25px;
        }
        .form-control:focus {
            background-color: #2a2a2a;
            color: #e0e0e0;
            box-shadow: 0 0 0 0.2rem rgba(255, 106, 0, 0.25);
        }
        .message {
            padding: 5px 0;
            margin-bottom: 10px;
        }
        .message.self {
            text-align: right;
        }
        .message .content {
            display: inline-block;
            max-width: 80%;
            word-wrap: break-word;
        }
        .message small {
            font-size: 0.75rem;
            color: #aaa;
        }
        #messages {
            height: 400px;
            overflow-y: auto;
            padding: 15px;
        }
        ::-webkit-scrollbar {
            width: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #1a1a1a;
        }
        ::-webkit-scrollbar-thumb {
            background-color: #ff6a00;
            border-radius: 4px;
        }

        @media (max-width: 768px) {
            body {
                background-size: cover;
            }
            .container {
                padding-left: 15px;
                padding-right: 15px;
            }
            .card {
                border-radius: 10px;
            }
            h1.h3 {
                font-size: 1.5rem;
            }
            #messages {
                height: 600px;
            }
            .btn-orange {
                padding: 8px 15px;
                font-size: 0.9rem;
            }
            .form-control {
                border-radius: 20px;
                padding: 10px;
            }
        }
    </style>
</head>
<body>
    <div class="overlay">
        <div class="container py-3">
            <div class="row justify-content-center">
                <div class="col-md-8">
                    <div class="card shadow-lg">
                        <div class="card-header bg-dark d-flex justify-content-between align-items-center">
                            <h1 class="h3 mb-0 text-orange">NightOwl Chat</h1>
                            <img src="/static/Designer.png" alt="NightOwl Logo" class="rounded-circle" width="40" height="40">
                        </div>
                        <div class="card-body">
                            <div id="login-form" class="mb-4">
                                <center><input type="text" id="client_id" class="form-control mb-2 w-50" placeholder="Enter your nickname"></center>
                                <center><button onclick="connectWebSocket()" class="btn btn-orange w-30">Join the Night</button></center>
                            </div>

                            <div id="chat-interface" class="d-none">
                                <div id="messages" class="mb-3 bg-dark rounded"></div>
                                <div class="input-group">
                                    <input type="text" id="message" class="form-control" placeholder="Whisper into the night...">
                                    <button onclick="sendMessage()" class="btn btn-orange">Send</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let socket;
        let clientId;

        function connectWebSocket() {
            clientId = document.getElementById("client_id").value.trim();
            if (!clientId) {
                alert("Please enter a valid name.");
                return;
            }

            document.getElementById("login-form").classList.add("d-none");
            document.getElementById("chat-interface").classList.remove("d-none");

            const ws_url = `ws://${window.location.host}/ws/${encodeURIComponent(clientId)}`;
            socket = new WebSocket(ws_url);

            socket.onopen = function(event) {
                console.log("WebSocket connection established.");
            };

            socket.onmessage = function(event) {
                const message = JSON.parse(event.data);
                displayMessage(message);
            };

            socket.onerror = function(event) {
                console.error("WebSocket error observed:", event);
            };

            socket.onclose = function(event) {
                console.log("WebSocket connection closed.");
            };
        }

        function sendMessage() {
            const messageInput = document.getElementById("message");
            const message = messageInput.value.trim();
            if (message && socket && socket.readyState === WebSocket.OPEN) {
                socket.send(message);
                messageInput.value = "";
            }
        }

        function formatTime(date) {
            let hours = date.getHours();
            const minutes = date.getMinutes().toString().padStart(2, '0');
            const ampm = hours >= 12 ? 'PM' : 'AM';
            hours = hours % 12 || 12;
            return `${hours}:${minutes} ${ampm}`;
        }
        
        function displayMessage(message) {
            const messagesDiv = document.getElementById("messages");
            const messageElement = document.createElement("div");
            messageElement.className = "message";
            
            if (message.client_id === "System") {
                messageElement.className += " text-muted fst-italic";
            } else if (message.client_id === clientId) {
                messageElement.className += " self";
            }
        
            messageElement.innerHTML = `
                <div class="content">
                    <span>${message.content}</span>
                    <small class="text-muted d-block mt-1">${message.client_id} • ${formatTime(new Date(message.timestamp))}</small>
                </div>
            `;
            messagesDiv.appendChild(messageElement);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        document.getElementById("message").addEventListener("keypress", function(event) {
            if (event.key === "Enter") {
                sendMessage();
            }
        });
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def get():
    return HTMLResponse(content=HTML_TEMPLATE)

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    try:
        history = await manager.get_message_history()
        for msg in history:
            await manager.send_personal_message(json.dumps(msg.dict()), client_id)

        while True:
            data = await websocket.receive_text()
            message = Message(
                client_id=client_id,
                content=data,
                timestamp=datetime.now().isoformat()
            )
            await manager.add_to_history(message)
            await manager.broadcast(json.dumps(message.dict()))
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        disconnect_message = {
            "client_id": "System",
            "content": f"{client_id} has left the chat",
            "timestamp": datetime.now().isoformat()
        }
        await manager.broadcast(json.dumps(disconnect_message))
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
