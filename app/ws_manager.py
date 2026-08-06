from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()
