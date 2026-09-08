# backend/app/websocket/manager.py
"""
WebSocket connection manager - designed for real-time event push, but not
currently wired to anything. Phase 12 honesty-audit note: nothing in this
codebase imports this module (backend/app/main.py defines its own separate,
simpler ConnectionManager and uses that instead), and no backend event
(a new observation, alert, or congestion change) ever calls broadcast()/
broadcast_event() on either manager. There is no live push functionality in
this app today - every page in the frontend fetches once per page load/
action, nothing subscribes over WebSocket. This is future-work scaffolding,
not a working real-time capability.
"""

from typing import Dict, List, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime, timezone


class ConnectionManager:
    """Manages WebSocket connections. See module docstring - not currently used anywhere."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_metadata: Dict[int, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: Optional[int] = None):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_metadata[id(websocket)] = {
            "user_id": user_id,
            "connected_at": datetime.now(timezone.utc)
        }
    
    def disconnect(self, websocket: WebSocket):
        """Remove a disconnected WebSocket."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if id(websocket) in self.connection_metadata:
            del self.connection_metadata[id(websocket)]
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific client."""
        try:
            await websocket.send_json(message)
        except WebSocketDisconnect:
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                disconnected.append(connection)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)
    
    async def send_to_user(self, user_id: int, message: dict):
        """Send a message to all connections for a specific user."""
        for connection in self.active_connections:
            meta = self.connection_metadata.get(id(connection), {})
            if meta.get("user_id") == user_id:
                try:
                    await connection.send_json(message)
                except WebSocketDisconnect:
                    self.disconnect(connection)
    
    async def broadcast_event(self, event_type: str, data: dict):
        """Broadcast a typed event to all clients."""
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await self.broadcast(message)


manager = ConnectionManager()
