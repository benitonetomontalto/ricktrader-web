"""
Rotas de Diagnóstico - IQ Option
Endpoints para diagnosticar problemas de conexão
"""
from fastapi import APIRouter, Depends
from app.core.auth import get_current_user
import socket
import ssl
import platform
import os
from datetime import datetime
import asyncio

router = APIRouter()

@router.get("/diagnostic/system")
async def diagnostic_system(current_user: dict = Depends(get_current_user)):
    """Informações do sistema"""
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "timestamp": datetime.now().isoformat()
    }

@router.get("/diagnostic/network")
async def diagnostic_network(current_user: dict = Depends(get_current_user)):
    """Diagnóstico de rede"""
    results = {
        "proxy": {
            "http": os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy'),
            "https": os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy'),
            "detected": bool(os.environ.get('HTTP_PROXY') or os.environ.get('HTTPS_PROXY'))
        },
        "dns": {},
        "port_443": {},
        "ssl_tls": {}
    }

    # Teste DNS
    try:
        ip_info = socket.getaddrinfo('iqoption.com', 443)
        results["dns"] = {
            "status": "success",
            "resolved": True,
            "ips": [info[4][0] for info in ip_info[:3]]
        }
    except Exception as e:
        results["dns"] = {
            "status": "error",
            "resolved": False,
            "error": str(e),
            "suggestion": "Verificar internet ou DNS"
        }

    # Teste Porta 443
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('iqoption.com', 443))
        sock.close()

        results["port_443"] = {
            "status": "success" if result == 0 else "error",
            "open": result == 0,
            "error_code": result if result != 0 else None,
            "suggestion": "Liberar porta 443 no firewall" if result != 0 else None
        }
    except Exception as e:
        results["port_443"] = {
            "status": "error",
            "open": False,
            "error": str(e)
        }

    # Teste SSL/TLS
    try:
        context = ssl.create_default_context()
        with socket.create_connection(('iqoption.com', 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname='iqoption.com') as ssock:
                cert = ssock.getpeercert()
                results["ssl_tls"] = {
                    "status": "success",
                    "working": True,
                    "tls_version": ssock.version(),
                    "cipher": ssock.cipher()[0],
                    "cert_valid_until": cert.get('notAfter')
                }
    except ssl.SSLError as e:
        results["ssl_tls"] = {
            "status": "error",
            "working": False,
            "error": str(e),
            "suggestion": "Atualizar Windows, sincronizar hora/data"
        }
    except Exception as e:
        results["ssl_tls"] = {
            "status": "error",
            "working": False,
            "error": str(e)
        }

    return results

@router.get("/diagnostic/iqoption-libraries")
async def diagnostic_libraries(current_user: dict = Depends(get_current_user)):
    """Verificar bibliotecas IQ Option"""
    libraries = {}

    # Verificar iqoptionapi
    try:
        import iqoptionapi
        libraries["iqoptionapi"] = {
            "installed": True,
            "version": getattr(iqoptionapi, '__version__', 'unknown')
        }
    except ImportError as e:
        libraries["iqoptionapi"] = {
            "installed": False,
            "error": str(e),
            "critical": True
        }

    # Verificar websocket
    try:
        import websocket
        libraries["websocket"] = {
            "installed": True,
            "version": getattr(websocket, '__version__', 'unknown')
        }
    except ImportError as e:
        libraries["websocket"] = {
            "installed": False,
            "error": str(e),
            "critical": True
        }

    # Verificar requests
    try:
        import requests
        libraries["requests"] = {
            "installed": True,
            "version": requests.__version__
        }
    except ImportError as e:
        libraries["requests"] = {
            "installed": False,
            "error": str(e),
            "critical": False
        }

    return libraries

@router.get("/diagnostic/full")
async def diagnostic_full(current_user: dict = Depends(get_current_user)):
    """Diagnóstico completo"""
    system = await diagnostic_system(current_user)
    network = await diagnostic_network(current_user)
    libraries = await diagnostic_libraries(current_user)

    # Análise geral
    issues = []
    warnings = []

    if not network["dns"].get("resolved"):
        issues.append({
            "type": "critical",
            "area": "DNS",
            "message": "Não consegue resolver iqoption.com",
            "solution": "Verificar conexão com internet"
        })

    if not network["port_443"].get("open"):
        issues.append({
            "type": "critical",
            "area": "Firewall",
            "message": "Porta 443 (HTTPS) está bloqueada",
            "solution": "Adicionar exceção no firewall para Rick Trader"
        })

    if not network["ssl_tls"].get("working"):
        issues.append({
            "type": "critical",
            "area": "SSL/TLS",
            "message": "Problema com certificados SSL",
            "solution": "Atualizar Windows e sincronizar hora/data do sistema"
        })

    if network["proxy"].get("detected"):
        warnings.append({
            "type": "warning",
            "area": "Proxy",
            "message": "Proxy detectado - pode interferir na conexão",
            "solution": "Verificar configurações de proxy"
        })

    for lib_name, lib_info in libraries.items():
        if not lib_info.get("installed") and lib_info.get("critical"):
            issues.append({
                "type": "critical",
                "area": "Bibliotecas",
                "message": f"Biblioteca {lib_name} não encontrada",
                "solution": "Reinstalar Rick Trader"
            })

    # Status geral
    overall_status = "healthy"
    if issues:
        overall_status = "critical"
    elif warnings:
        overall_status = "warning"

    return {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "system": system,
        "network": network,
        "libraries": libraries,
        "issues": issues,
        "warnings": warnings,
        "can_connect_iqoption": len([i for i in issues if i["type"] == "critical"]) == 0
    }

@router.post("/diagnostic/test-connection")
async def test_iqoption_connection(current_user: dict = Depends(get_current_user)):
    """Testar conexão real com IQ Option usando sessão atual"""
    from app.services.session_manager import get_session_manager

    session_manager = get_session_manager()
    client = session_manager.get_client(current_user["username"])

    if not client:
        return {
            "connected": False,
            "error": "Cliente IQ Option não inicializado",
            "suggestion": "Faça login com suas credenciais IQ Option primeiro"
        }

    if not client.is_connected:
        return {
            "connected": False,
            "error": "Cliente não está conectado",
            "last_error": client.last_error,
            "suggestion": "Tente reconectar nas configurações"
        }

    # Testar operação real
    try:
        balance_info = await client.get_balance()
        pairs = await client.get_available_pairs(include_otc=True)

        return {
            "connected": True,
            "working": True,
            "account_type": client.account_type,
            "balance": balance_info.get("balance") if isinstance(balance_info, dict) else balance_info,
            "pairs_available": len(pairs),
            "message": "Conexão IQ Option funcionando perfeitamente!"
        }
    except Exception as e:
        return {
            "connected": client.is_connected,
            "working": False,
            "error": str(e),
            "suggestion": "Problema ao comunicar com IQ Option API"
        }
