"""
WebSocket Connection Manager
Gerencia conexões WebSocket para transmissão de sinais em tempo real
"""
from typing import List
from fastapi import WebSocket
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Gerenciador de conexões WebSocket"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Aceitar nova conexão WebSocket"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Nova conexão WebSocket. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remover conexão WebSocket"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Conexão WebSocket removida. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Transmitir mensagem para todas as conexões ativas"""
        if not self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem: {e}")
                disconnected.append(connection)

        # Remover conexões desconectadas
        for connection in disconnected:
            self.disconnect(connection)

    async def send_signal(self, signal_data: dict):
        """Enviar novo sinal para todos os clientes conectados"""
        message = {
            "type": "new_signal",
            "data": signal_data
        }
        await self.broadcast(message)
        logger.info(f"Sinal transmitido para {len(self.active_connections)} clientes")


# Instância global do gerenciador
manager = ConnectionManager()
