"""Encryption utilities for secure credential storage"""
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os
from typing import Optional

# This should be stored in environment variables in production
# For now, we'll use a default key (NOT SECURE FOR PRODUCTION!)
SECRET_KEY = os.getenv("ENCRYPTION_SECRET", "binary-options-trading-system-secret-key-2024")


class CredentialEncryption:
    """Handles encryption/decryption of sensitive credentials"""

    def __init__(self, secret_key: Optional[str] = None):
        """Initialize encryption with a secret key"""
        self.secret_key = secret_key or SECRET_KEY
        self.cipher = self._create_cipher()

    def _create_cipher(self) -> Fernet:
        """Create Fernet cipher from secret key"""
        # Derive a proper key from the secret
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"iqoption-salt",  # Static salt (not ideal but ok for this use case)
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.secret_key.encode()))
        return Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string"""
        encrypted = self.cipher.encrypt(plaintext.encode())
        return encrypted.decode()

    def decrypt(self, encrypted: str) -> str:
        """Decrypt a string"""
        decrypted = self.cipher.decrypt(encrypted.encode())
        return decrypted.decode()


# Global instance
_encryption: Optional[CredentialEncryption] = None


def get_encryption() -> CredentialEncryption:
    """Get the global encryption instance"""
    global _encryption
    if _encryption is None:
        _encryption = CredentialEncryption()
    return _encryption
