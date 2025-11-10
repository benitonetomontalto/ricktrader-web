"""
Access token management for controlling system usage.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from threading import Lock
from typing import Dict, Optional, Tuple, Iterable

from .config import settings


class AccessTokenManager:
    """Load, validate and persist access tokens for the platform."""

    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self._lock = Lock()
        self._tokens: Dict[str, dict] = {}
        self._load_tokens()

    def _load_tokens(self) -> None:
        """Load tokens from storage, creating file if necessary."""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w", encoding="utf-8") as fp:
                json.dump({}, fp, indent=2, ensure_ascii=False)
            self._tokens = {}
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if isinstance(data, dict):
                self._tokens = data
            else:
                self._tokens = {}
        except json.JSONDecodeError:
            # Corrupted file – start fresh to avoid blocking logins.
            self._tokens = {}

    def _save_tokens(self) -> None:
        """Persist token information back to storage."""
        with open(self.storage_path, "w", encoding="utf-8") as fp:
            json.dump(self._tokens, fp, indent=2, ensure_ascii=False, default=str)

    def refresh(self) -> None:
        """Reload tokens from disk (useful if file was edited manually)."""
        with self._lock:
            self._load_tokens()

    def _get_token(self, token_value: str) -> Optional[dict]:
        return self._tokens.get(token_value)

    def validate_and_register(
        self,
        token_value: str,
        username: str,
        iq_email: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Validate a token, registering the user if allowed.

        Returns:
            (success, message)
        """
        with self._lock:
            token = self._get_token(token_value)
            if token is None:
                return False, "Token de acesso inválido."

            if not token.get("active", True):
                return False, "Token de acesso desativado. Solicite um novo ao administrador."

            expires_at = token.get("expires_at")
            if expires_at:
                try:
                    expires_dt = datetime.fromisoformat(expires_at)
                    if expires_dt < datetime.utcnow():
                        return False, "Token expirado. Solicite um novo ao administrador."
                except ValueError:
                    # Ignore malformed expiry, but notify via message.
                    return False, "Token inválido (data de expiração incorreta)."

            users = token.setdefault("users", {})
            max_users = token.get("max_users")

            # If the username is already registered, update metadata and allow access.
            existing = users.get(username)
            if existing:
                existing["last_login"] = datetime.utcnow().isoformat()
                if iq_email:
                    existing["iq_email"] = iq_email
                self._save_tokens()
                return True, "Acesso autorizado."

            # Check if user with same email already exists (case: different username, same email)
            if iq_email:
                for user_key, user_data in users.items():
                    if user_data.get("iq_email") == iq_email:
                        # Same email found, update username and allow access
                        user_data["last_login"] = datetime.utcnow().isoformat()
                        # Update the username key if different
                        if user_key != username:
                            users[username] = user_data
                            users.pop(user_key)
                        self._save_tokens()
                        return True, "Acesso autorizado."

            # Enforce max users per token.
            if max_users is not None:
                active_user_count = len(users)
                if active_user_count >= max_users:
                    return False, "Limite de usuários atingido para este token."

            # Register new user for this token and persist.
            users[username] = {
                "created_at": datetime.utcnow().isoformat(),
                "last_login": datetime.utcnow().isoformat(),
                "iq_email": iq_email,
            }
            self._save_tokens()
            return True, "Acesso autorizado."

    def deactivate_token(self, token_value: str) -> bool:
        """Deactivate a token so it can no longer be used."""
        with self._lock:
            token = self._get_token(token_value)
            if token is None:
                return False
            token["active"] = False
            self._save_tokens()
            return True

    def activate_token(self, token_value: str) -> bool:
        """Reactivate a token."""
        with self._lock:
            token = self._get_token(token_value)
            if token is None:
                return False
            token["active"] = True
            self._save_tokens()
            return True

    def create_token(
        self,
        token_value: str,
        label: Optional[str] = None,
        max_users: Optional[int] = None,
        notes: Optional[str] = None,
        active: bool = True,
        expires_at: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Create a new access token entry.

        Returns:
            (success, message)
        """
        with self._lock:
            if token_value in self._tokens:
                return False, "Token jǭ existe."

            token_data = {
                "label": label,
                "active": active,
                "max_users": max_users,
                "users": {},
                "notes": notes,
            }
            if expires_at:
                token_data["expires_at"] = expires_at

            self._tokens[token_value] = token_data
            self._save_tokens()
            return True, "Token criado com sucesso."

    def list_tokens(self) -> Iterable[Tuple[str, dict]]:
        """Return a snapshot iterator with token data."""
        with self._lock:
            return list(self._tokens.items())

    def remove_user(self, token_value: str, username: str) -> bool:
        """Remove a user assignment from a token."""
        with self._lock:
            token = self._get_token(token_value)
            if token is None:
                return False
            users = token.get("users", {})
            if username not in users:
                return False
            users.pop(username)
            self._save_tokens()
            return True

    def get_token_snapshot(self) -> Dict[str, dict]:
        """Return a shallow copy of token information (for admin inspection)."""
        with self._lock:
            return json.loads(json.dumps(self._tokens))

    def get_token_label(self, token_value: str) -> Optional[str]:
        """Return human-readable label for a token, if any."""
        with self._lock:
            token = self._get_token(token_value)
            if token is None:
                return None
            return token.get("label")


# Global instance
access_token_manager = AccessTokenManager(settings.ACCESS_TOKENS_FILE)
