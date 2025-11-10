"""
Sistema de Validação de Licenças Remoto
Conecta com servidor de licenças externo
"""
import requests
import hashlib
import platform
import uuid
from typing import Tuple, Optional
from datetime import datetime
import os

class RemoteLicenseManager:
    """Gerenciador de licenças remoto"""

    def __init__(self, server_url: Optional[str] = None):
        """
        Inicializar gerenciador de licenças remoto

        Args:
            server_url: URL do servidor de licenças (ex: http://192.168.1.100:8001)
        """
        # URL do servidor - pode ser configurada via env ou parâmetro
        self.server_url = server_url or os.getenv("LICENSE_SERVER_URL", "http://localhost:8001")
        self.timeout = 10  # segundos

    def get_machine_id(self) -> str:
        """
        Obter ID único da máquina

        Returns:
            Machine ID único
        """
        try:
            # Tentar obter UUID do hardware
            machine_uuid = uuid.UUID(int=uuid.getnode())
            return str(machine_uuid)
        except:
            # Fallback: usar informações do sistema
            system_info = f"{platform.node()}-{platform.machine()}-{platform.processor()}"
            return hashlib.sha256(system_info.encode()).hexdigest()[:16].upper()

    def validate_license(
        self,
        token: str,
        username: str,
        iqoption_email: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Validar licença com servidor remoto

        Args:
            token: Token de licença
            username: Nome de usuário
            iqoption_email: Email do IQ Option (opcional)

        Returns:
            Tuple (válido, mensagem)
        """
        try:
            machine_id = self.get_machine_id()

            # Fazer requisição ao servidor
            response = requests.post(
                f"{self.server_url}/api/licenses/validate",
                json={
                    "token": token,
                    "username": username,
                    "machine_id": machine_id,
                    "iqoption_email": iqoption_email
                },
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()

                if data.get("valid"):
                    label = data.get("label", "")
                    expires_at = data.get("expires_at")

                    message = f"Licença válida: {label}"
                    if expires_at:
                        try:
                            exp_date = datetime.fromisoformat(expires_at)
                            message += f" (Expira em: {exp_date.strftime('%d/%m/%Y')})"
                        except:
                            pass

                    return True, message
                else:
                    return False, data.get("message", "Licença inválida")

            else:
                return False, f"Erro no servidor: {response.status_code}"

        except requests.exceptions.ConnectionError:
            # Servidor offline - modo offline
            return False, "Servidor de licenças offline. Verifique sua conexão ou contate o suporte."
        except requests.exceptions.Timeout:
            return False, "Timeout ao conectar com servidor de licenças"
        except Exception as e:
            return False, f"Erro ao validar licença: {str(e)}"

    def test_connection(self) -> Tuple[bool, str]:
        """
        Testar conexão com servidor de licenças

        Returns:
            Tuple (conectado, mensagem)
        """
        try:
            response = requests.get(
                f"{self.server_url}/health",
                timeout=5
            )

            if response.status_code == 200:
                return True, "Servidor de licenças online"
            else:
                return False, f"Servidor respondeu com status {response.status_code}"

        except requests.exceptions.ConnectionError:
            return False, "Não foi possível conectar ao servidor de licenças"
        except Exception as e:
            return False, f"Erro: {str(e)}"

    def get_token_label(self, token: str) -> str:
        """
        Obter label do token (nome amigável)

        Args:
            token: Token de licença

        Returns:
            Label do token
        """
        # Implementação simplificada - retorna o próprio token
        return token


# Instância global
_remote_license_manager = None


def get_remote_license_manager() -> RemoteLicenseManager:
    """Obter instância do gerenciador de licenças remoto"""
    global _remote_license_manager
    if _remote_license_manager is None:
        _remote_license_manager = RemoteLicenseManager()
    return _remote_license_manager
