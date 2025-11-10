"""IQ Option Session Manager - Multi-user support"""
import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging
import pandas as pd

from ..scanner.iqoption_client import IQOptionClient

logger = logging.getLogger(__name__)


class IQOptionSessionManager:
    """Manages multiple IQ Option sessions for different users"""

    def __init__(self):
        self.sessions: Dict[str, IQOptionClient] = {}
        self.session_timeouts: Dict[str, datetime] = {}
        self.account_types: Dict[str, str] = {}
        self.cleanup_task: Optional[asyncio.Task] = None
        self.timeout_minutes = 30  # Session timeout

    async def start(self):
        """Start the session manager"""
        logger.info("Starting IQ Option Session Manager")
        self.cleanup_task = asyncio.create_task(self._cleanup_sessions())

    async def stop(self):
        """Stop the session manager"""
        logger.info("Stopping IQ Option Session Manager")

        if self.cleanup_task:
            self.cleanup_task.cancel()
            self.cleanup_task = None

        for username in list(self.sessions.keys()):
            await self.disconnect_user(username)

    async def connect_user(
        self,
        username: str,
        email: str,
        password: str,
        account_type: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Connect a user to IQ Option

        Returns:
            (success, message)
        """
        try:
            if username in self.sessions:
                client = self.sessions[username]

                if account_type:
                    client.set_account_type(account_type)

                if client.awaiting_two_factor:
                    logger.info("User %s still has a pending IQ Option 2FA challenge", username)
                    message = client.two_factor_message or "Verificacao IQ Option pendente."
                    return False, message

                if await client.check_connection():
                    logger.info("Reusing existing IQ Option session for %s", username)
                    self.session_timeouts[username] = datetime.now()

                    if account_type:
                        await client.connect(account_type=account_type)
                        self.account_types[username] = client.account_type
                        return True, f"Sessao ja ativa na conta {client.account_type}"

                    return True, "Sessao ja ativa"

                await self.disconnect_user(username)

            client = IQOptionClient(
                email=email,
                password=password,
                account_type=account_type
            )
            success = await client.connect(account_type=account_type)
            message = (
                f"Conectado ao IQ Option ({client.account_type})"
                if success else client.last_error or "Falha ao conectar"
            )

            if client.awaiting_two_factor:
                self.sessions[username] = client
                self.session_timeouts[username] = datetime.now()
                self.account_types[username] = client.account_type
                pending_message = client.two_factor_message or "Verificacao pendente."
                logger.info("User %s pending IQ Option 2FA", username)
                return False, pending_message

            if success:
                self.sessions[username] = client
                self.session_timeouts[username] = datetime.now()
                self.account_types[username] = client.account_type
                logger.info("User %s connected to IQ Option", username)
            else:
                logger.error("Failed to connect %s to IQ Option: %s", username, message)

            return success, message

        except Exception as exc:
            logger.exception("Connection error for %s: %s", username, exc)
            return False, str(exc)

    async def disconnect_user(self, username: str) -> bool:
        """Disconnect a user from IQ Option"""
        try:
            if username in self.sessions:
                client = self.sessions[username]
                await client.disconnect()
                del self.sessions[username]
                self.session_timeouts.pop(username, None)
                self.account_types.pop(username, None)
                logger.info("User %s disconnected from IQ Option", username)
                return True
            return False

        except Exception as exc:
            logger.error("Disconnect error for %s: %s", username, exc)
            return False

    async def complete_two_factor(self, username: str, code: str) -> tuple[bool, str]:
        """Complete a pending 2FA verification for a user."""
        client = self.sessions.get(username)
        if not client:
            return False, "Sessao IQ Option nao encontrada."

        try:
            success, message = await client.submit_two_factor_code(code)
            if success:
                self.session_timeouts[username] = datetime.now()
                self.account_types[username] = client.account_type
                logger.info("User %s completed IQ Option 2FA", username)
            else:
                if not client.awaiting_two_factor:
                    await self.disconnect_user(username)
            return success, message
        except Exception as exc:
            logger.exception("2FA completion error for %s: %s", username, exc)
            return False, str(exc)

    def get_client(self, username: str) -> Optional[IQOptionClient]:
        """Get IQ Option client for a user"""
        client = self.sessions.get(username)
        if client:
            self.session_timeouts[username] = datetime.now()
        return client

    def is_connected(self, username: str) -> bool:
        """Check if user is connected"""
        client = self.sessions.get(username)
        return bool(client and client.is_connected)

    async def get_user_balance(self, username: str) -> Optional[float]:
        """Get balance for a user"""
        client = self.get_client(username)
        if not client:
            return None

        balance_info = await client.get_balance()
        if isinstance(balance_info, dict):
            return balance_info.get("balance")
        return balance_info

    async def get_user_pairs(self, username: str):
        """Get available pairs for a user"""
        client = self.get_client(username)
        if client:
            return await client.get_available_pairs(include_otc=True)
        return []

    def get_user_account_type(self, username: str) -> Optional[str]:
        """Return stored account type for a user"""
        if username in self.sessions:
            return self.sessions[username].account_type
        return self.account_types.get(username)

    async def get_user_candles(
        self,
        username: str,
        symbol: str,
        timeframe: int = 60,
        count: int = 100
    ):
        """Get candles for a user. Timeframe expected in seconds."""
        client = self.get_client(username)
        if not client:
            return None

        timeframe_seconds = max(timeframe, 60)
        timeframe_minutes = max(1, timeframe_seconds // 60)

        candles = await client.get_candles(symbol, timeframe_minutes, count)
        if not candles:
            return None

        if isinstance(candles, pd.DataFrame):
            return candles

        return pd.DataFrame(candles)

    def get_active_sessions(self) -> list:
        """Get list of active sessions"""
        return [
            {
                "username": username,
                "email": client.email,
                "last_activity": self.session_timeouts.get(username),
            }
            for username, client in self.sessions.items()
        ]

    async def _cleanup_sessions(self):
        """Background task to cleanup inactive sessions"""
        while True:
            try:
                await asyncio.sleep(60)
                now = datetime.now()
                timeout_threshold = now - timedelta(minutes=self.timeout_minutes)

                inactive_users = [
                    username
                    for username, last_activity in self.session_timeouts.items()
                    if last_activity < timeout_threshold
                ]

                for username in inactive_users:
                    logger.info("Disconnecting inactive IQ Option session: %s", username)
                    await self.disconnect_user(username)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Cleanup task error: %s", exc)


_session_manager: Optional[IQOptionSessionManager] = None


def get_session_manager() -> IQOptionSessionManager:
    """Return singleton session manager"""
    global _session_manager
    if _session_manager is None:
        _session_manager = IQOptionSessionManager()
    return _session_manager
