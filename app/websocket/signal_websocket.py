"""
WebSocket handler for real-time signal updates
"""
import json
import asyncio
from typing import Set
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class SignalWebSocketManager:
    """Manage WebSocket connections for real-time signal updates"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"[WebSocket] Nova conexão. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        self.active_connections.discard(websocket)
        print(f"[WebSocket] Conexão fechada. Total: {len(self.active_connections)}")

    async def broadcast_signal(self, signal_data: dict):
        """
        Broadcast signal to all connected clients

        Args:
            signal_data: Signal data to broadcast
        """
        if not self.active_connections:
            return

        message = json.dumps({
            "type": "new_signal",
            "data": signal_data
        }, cls=DateTimeEncoder)

        # Send to all connections
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"[WebSocket] Erro ao enviar: {e}")
                disconnected.add(connection)

        # Remove disconnected clients
        self.active_connections -= disconnected

    async def broadcast_scanner_status(self, status: dict):
        """Broadcast scanner status update"""
        if not self.active_connections:
            return

        message = json.dumps({
            "type": "scanner_status",
            "data": status
        }, cls=DateTimeEncoder)

        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.add(connection)

        self.active_connections -= disconnected

    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """Send message to specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"[WebSocket] Erro ao enviar mensagem pessoal: {e}")


# Global WebSocket manager
ws_manager = SignalWebSocketManager()
