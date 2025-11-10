"""
Admin Routes - Gerenciamento de Tokens
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import secrets
import json
import os

from ..core.token_manager import access_token_manager

router = APIRouter(prefix="/admin", tags=["Admin"])

# Função para carregar credenciais de admin
def load_admin_credentials():
    """Carrega credenciais de admin do arquivo"""
    try:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
        credentials_file = os.path.join(data_dir, 'admin_credentials.json')

        if os.path.exists(credentials_file):
            with open(credentials_file, 'r') as f:
                return json.load(f)
        else:
            # Criar arquivo padrão
            os.makedirs(data_dir, exist_ok=True)
            default_creds = {
                "username": "admin",
                "password": "admin123",
                "note": "IMPORTANTE: Altere estas credenciais!"
            }
            with open(credentials_file, 'w') as f:
                json.dump(default_creds, f, indent=2)
            return default_creds
    except Exception as e:
        print(f"Erro ao carregar credenciais: {e}")
        return {"username": "admin", "password": "admin123"}

def save_admin_credentials(username: str, password: str):
    """Salva novas credenciais de admin"""
    try:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
        credentials_file = os.path.join(data_dir, 'admin_credentials.json')
        os.makedirs(data_dir, exist_ok=True)

        with open(credentials_file, 'w') as f:
            json.dump({
                "username": username,
                "password": password,
                "note": "Credenciais personalizadas"
            }, f, indent=2)
        return True
    except Exception as e:
        print(f"Erro ao salvar credenciais: {e}")
        return False

# Dependência para verificar autenticação
async def verify_admin_auth(authorization: Optional[str] = Header(None)):
    """Verifica se as credenciais de admin são válidas"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Autenticação necessária")

    try:
        # Formato esperado: "Basic username:password"
        if not authorization.startswith("Basic "):
            raise HTTPException(status_code=401, detail="Formato de autenticação inválido")

        import base64
        credentials = base64.b64decode(authorization.replace("Basic ", "")).decode('utf-8')
        username, password = credentials.split(":", 1)

        # Verificar credenciais
        admin_creds = load_admin_credentials()
        if username != admin_creds["username"] or password != admin_creds["password"]:
            raise HTTPException(status_code=401, detail="Credenciais inválidas")

        return True
    except HTTPException:
        raise
    except Exception as e:
        print(f"Erro na autenticação: {e}")
        raise HTTPException(status_code=401, detail="Erro na autenticação")

class AdminLoginRequest(BaseModel):
    username: str
    password: str

class AdminLoginResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_username: str
    new_password: str

@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(request: AdminLoginRequest):
    """
    Login do administrador

    Args:
        request: Credenciais de login

    Returns:
        Token de autenticação
    """
    admin_creds = load_admin_credentials()

    if request.username == admin_creds["username"] and request.password == admin_creds["password"]:
        # Gerar token simples (Base64 encoded credentials)
        import base64
        token = base64.b64encode(f"{request.username}:{request.password}".encode()).decode()

        return AdminLoginResponse(
            success=True,
            message="Login realizado com sucesso",
            token=token
        )
    else:
        return AdminLoginResponse(
            success=False,
            message="Credenciais inválidas"
        )

@router.post("/change-password")
async def change_admin_password(request: ChangePasswordRequest, authenticated: bool = Depends(verify_admin_auth)):
    """
    Alterar credenciais de admin

    Args:
        request: Nova senha

    Returns:
        Status da operação
    """
    admin_creds = load_admin_credentials()

    # Verificar senha atual
    if request.current_password != admin_creds["password"]:
        raise HTTPException(status_code=400, detail="Senha atual incorreta")

    # Salvar novas credenciais
    if save_admin_credentials(request.new_username, request.new_password):
        return {"status": "success", "message": "Credenciais alteradas com sucesso"}
    else:
        raise HTTPException(status_code=500, detail="Erro ao salvar credenciais")

class CreateTokenRequest(BaseModel):
    token_value: Optional[str] = None  # Se None, gera automaticamente
    label: str
    max_users: Optional[int] = None
    notes: Optional[str] = None
    expires_days: Optional[int] = None

class TokenResponse(BaseModel):
    token_value: str
    label: Optional[str]
    active: bool
    max_users: Optional[int]
    users_count: int
    notes: Optional[str]
    expires_at: Optional[str]

@router.post("/tokens", response_model=TokenResponse)
async def create_token(request: CreateTokenRequest, authenticated: bool = Depends(verify_admin_auth)):
    """
    Criar novo token de acesso

    Args:
        request: Dados do token

    Returns:
        Token criado
    """
    # Gerar token se não fornecido
    token_value = request.token_value or f"RICK-{secrets.token_urlsafe(16)}"

    # Calcular data de expiração
    expires_at = None
    if request.expires_days:
        expires_dt = datetime.utcnow() + timedelta(days=request.expires_days)
        expires_at = expires_dt.isoformat()

    # Criar token
    success, message = access_token_manager.create_token(
        token_value=token_value,
        label=request.label,
        max_users=request.max_users,
        notes=request.notes,
        active=True,
        expires_at=expires_at
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Retornar token criado
    tokens = dict(access_token_manager.list_tokens())
    token_data = tokens[token_value]

    return TokenResponse(
        token_value=token_value,
        label=token_data.get("label"),
        active=token_data.get("active", True),
        max_users=token_data.get("max_users"),
        users_count=len(token_data.get("users", {})),
        notes=token_data.get("notes"),
        expires_at=token_data.get("expires_at")
    )

@router.get("/tokens", response_model=List[TokenResponse])
async def list_tokens(authenticated: bool = Depends(verify_admin_auth)):
    """
    Listar todos os tokens

    Returns:
        Lista de tokens
    """
    tokens = []
    for token_value, token_data in access_token_manager.list_tokens():
        tokens.append(TokenResponse(
            token_value=token_value,
            label=token_data.get("label"),
            active=token_data.get("active", True),
            max_users=token_data.get("max_users"),
            users_count=len(token_data.get("users", {})),
            notes=token_data.get("notes"),
            expires_at=token_data.get("expires_at")
        ))

    return tokens

@router.post("/tokens/{token_value}/deactivate")
async def deactivate_token(token_value: str, authenticated: bool = Depends(verify_admin_auth)):
    """Desativar um token"""
    success = access_token_manager.deactivate_token(token_value)

    if not success:
        raise HTTPException(status_code=404, detail="Token não encontrado")

    return {"status": "success", "message": "Token desativado"}

@router.post("/tokens/{token_value}/activate")
async def activate_token(token_value: str, authenticated: bool = Depends(verify_admin_auth)):
    """Ativar um token"""
    success = access_token_manager.activate_token(token_value)

    if not success:
        raise HTTPException(status_code=404, detail="Token não encontrado")

    return {"status": "success", "message": "Token ativado"}

@router.delete("/tokens/{token_value}/users/{username}")
async def remove_user_from_token(token_value: str, username: str, authenticated: bool = Depends(verify_admin_auth)):
    """Remover usuário de um token"""
    success = access_token_manager.remove_user(token_value, username)

    if not success:
        raise HTTPException(status_code=404, detail="Token ou usuário não encontrado")

    return {"status": "success", "message": "Usuário removido"}
