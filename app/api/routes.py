"""
API Routes
"""
import asyncio
from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List, Optional, Dict
from datetime import datetime, timedelta

from ..models.schemas import (
    LoginRequest,
    TokenResponse,
    TradingPair,
    TradingSignal,
    ScanConfig,
    UserSettings,
    TradingStats,
    SignalResponse
)
from ..core.security import create_access_token, get_current_user
from ..core.token_manager import access_token_manager
from ..services.scanner.mboption_client import get_mboption_client
from ..services.scanner.market_data_client import get_market_data_client
from ..services.scanner.forex_data_client import get_forex_data_client
from ..services.scanner.forex_otc_client import get_forex_otc_client
from ..services.scanner.auto_scanner import AutoScanner
from ..services.scanner.signal_generator import SignalGenerator
from ..websocket.signal_websocket import ws_manager
from ..services.iqoption import get_session_manager

router = APIRouter()

# Global scanner instance (in production, use dependency injection)
_scanner_instances: Dict[str, AutoScanner] = {}
_scanner_tasks: Dict[str, asyncio.Task] = {}


@router.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Authenticate user and create access token

    Args:
        request: Login credentials

    Returns:
        Access token
    """
    if not request.access_token:
        raise HTTPException(status_code=403, detail="Token de acesso obrigatório.")

    # Auto-create user token if it's a license token (not GT4 format)
    if not request.access_token.startswith("GT4-"):
        print(f"[LOGIN] License token detected, auto-creating user token for {request.username}")
        # Create a user token automatically based on the license
        success, message = access_token_manager.create_token(
            token_value=f"GT4-LICENSE-{request.username[:8]}",
            label=f"Auto-created for {request.username}",
            max_users=1,
            notes=f"Auto-created from license for user {request.username}",
            active=True
        )
        if success:
            request.access_token = f"GT4-LICENSE-{request.username[:8]}"
            print(f"[LOGIN] Auto-created token: {request.access_token}")
        else:
            # Token already exists, reuse it
            request.access_token = f"GT4-LICENSE-{request.username[:8]}"
            print(f"[LOGIN] Reusing existing token: {request.access_token}")

    token_valid, token_message = access_token_manager.validate_and_register(
        request.access_token,
        request.username,
        request.iqoption_email
    )
    if not token_valid:
        raise HTTPException(status_code=403, detail=token_message)
    token_label = access_token_manager.get_token_label(request.access_token)

    # In production, validate credentials against database.
    # For now, accept any login for demonstration, protected by access tokens.

    user_data = {"user_id": request.username, "username": request.username}

    # Create access token
    access_token = create_access_token(data=user_data)

    iq_option_connected = False
    iq_option_message: Optional[str] = None
    iq_option_balance: Optional[float] = None
    iq_option_account_type: Optional[str] = None
    iq_option_two_factor_required: bool = False
    iq_option_two_factor_message: Optional[str] = None

    session_manager = get_session_manager()

    # Se credenciais IQ Option foram fornecidas, conectar à API real
    if hasattr(request, 'iqoption_email') and request.iqoption_email and hasattr(request, 'iqoption_password') and request.iqoption_password:
        print(f"[LOGIN] Conectando ao IQ Option com email: {request.iqoption_email}")

        try:
            requested_account_type = getattr(request, "iqoption_account_type", None)

            # Tenta conectar com o tipo de conta especificado
            connected, message = await session_manager.connect_user(
                username=request.username,
                email=request.iqoption_email,
                password=request.iqoption_password,
                account_type=requested_account_type
            )
            iq_option_connected = connected
            iq_option_message = message

            # Se falhou e um tipo específico foi solicitado, tenta o outro tipo automaticamente
            if not connected and requested_account_type:
                alternative_type = "PRACTICE" if requested_account_type.upper() == "REAL" else "REAL"
                print(f"[LOGIN] Primeira tentativa ({requested_account_type}) falhou. Tentando com {alternative_type}...")

                connected, message = await session_manager.connect_user(
                    username=request.username,
                    email=request.iqoption_email,
                    password=request.iqoption_password,
                    account_type=alternative_type
                )
                iq_option_connected = connected
                if connected:
                    iq_option_message = f"Conectado com sucesso usando conta {alternative_type} (tipo {requested_account_type} não disponível)"
                else:
                    iq_option_message = f"Falha em ambos os tipos de conta. REAL: {iq_option_message} | {alternative_type}: {message}"

            client = session_manager.get_client(request.username)
            if client and client.awaiting_two_factor:
                iq_option_two_factor_required = True
                iq_option_two_factor_message = client.two_factor_message
                iq_option_connected = False
                iq_option_message = client.two_factor_message or iq_option_message
            elif connected and client:
                print("[LOGIN] OK. Conectado ao IQ Option com sucesso!")
                balance_info = await client.get_balance()
                if isinstance(balance_info, dict):
                    iq_option_balance = balance_info.get("balance")
                    iq_option_account_type = client.account_type or balance_info.get("account_type")
                else:
                    iq_option_account_type = client.account_type
            elif not connected:
                print(f"[LOGIN] ERRO ao conectar ao IQ Option: {iq_option_message}")
        except Exception as e:
            iq_option_message = str(e)
            print(f"[LOGIN] ERRO ao conectar IQ Option: {e}")

    return TokenResponse(
        access_token=access_token,
        user_id=request.username,
        access_message=token_message,
        access_token_label=token_label,
        iq_option_connected=iq_option_connected,
        iq_option_message=iq_option_message,
        iq_option_balance=iq_option_balance,
        iq_option_account_type=iq_option_account_type,
        iq_option_two_factor_required=iq_option_two_factor_required,
        iq_option_two_factor_message=iq_option_two_factor_message
    )


@router.get("/pairs", response_model=List[TradingPair])
async def get_trading_pairs(include_otc: bool = True, current_user: dict = Depends(get_current_user)):
    """
    Get available trading pairs from REAL IQ Option API

    Args:
        include_otc: Include OTC pairs

    Returns:
        List of real trading pairs from IQ Option
    """
    session_manager = get_session_manager()
    client = session_manager.get_client(current_user["username"])

    if not client:
        raise HTTPException(status_code=400, detail="Usuário não conectado ao IQ Option.")

    if not client.is_connected:
        connected = await client.connect()
        if not connected:
            raise HTTPException(
                status_code=400,
                detail=client.last_error or "Não foi possível restabelecer conexão com a IQ Option."
            )

    pairs_data = await client.get_available_pairs(include_otc)

    pairs = [
        TradingPair(
            symbol=p['symbol'],
            name=p['name'],
            is_otc=p['is_otc'],
            is_active=p.get('is_active', True),
            market_type=p.get('type')
        )
        for p in pairs_data
    ]

    return pairs


@router.post("/scanner/start")
async def start_scanner(config: ScanConfig, current_user: dict = Depends(get_current_user)):
    """
    Start the automatic scanner with REAL IQ Option data

    Args:
        config: Scanner configuration

    Returns:
        Status message
    """
    username = current_user["username"]
    session_manager = get_session_manager()
    client = session_manager.get_client(username)

    if not client:
        raise HTTPException(status_code=400, detail="Usuário não conectado ao IQ Option.")

    if not client.is_connected:
        connected = await client.connect()
        if not connected:
            raise HTTPException(
                status_code=400,
                detail=client.last_error or "Não foi possível restabelecer conexão com a IQ Option."
            )

    if username in _scanner_instances:
        existing = _scanner_instances[username]
        if existing.is_running:
            existing.stop_scanning()
            await asyncio.sleep(0.1)

        existing_task = _scanner_tasks.get(username)
        if existing_task and not existing_task.done():
            existing_task.cancel()

    import importlib
    import sys
    if 'app.services.scanner.signal_generator' in sys.modules:
        importlib.reload(sys.modules['app.services.scanner.signal_generator'])
    if 'app.models.schemas' in sys.modules:
        importlib.reload(sys.modules['app.models.schemas'])

    print(f"[API] Iniciando scanner com config: {config.dict()}")
    scanner = AutoScanner(client, config)
    task = asyncio.create_task(scanner.start_scanning())
    _scanner_instances[username] = scanner
    _scanner_tasks[username] = task
    task.add_done_callback(lambda t, user=username: _scanner_tasks.pop(user, None))

    return {
        "status": "success",
        "message": "Scanner iniciado com IQ OPTION REAL!",
        "config": config.dict(),
        "data_source": "IQ Option - Real-Time Market Data"
    }

@router.post("/scanner/stop")
async def stop_scanner(current_user: dict = Depends(get_current_user)):
    """Stop the automatic scanner"""
    username = current_user["username"]
    scanner = _scanner_instances.get(username)

    if not scanner or not scanner.is_running:
        raise HTTPException(status_code=400, detail="Scanner não está em execução")

    scanner.stop_scanning()

    task = _scanner_tasks.get(username)
    if task and not task.done():
        task.cancel()
    _scanner_tasks.pop(username, None)

    return {
        "status": "success",
        "message": "Scanner interrompido"
    }

@router.get("/scanner/status")
async def get_scanner_status(current_user: dict = Depends(get_current_user)):
    """Get scanner status"""
    username = current_user["username"]
    scanner = _scanner_instances.get(username)

    if not scanner:
        return {
            "is_running": False,
            "signals_count": 0
        }

    return {
        "is_running": scanner.is_running,
        "signals_count": len(scanner.latest_signals)
    }

@router.get("/signals", response_model=List[TradingSignal])
async def get_signals(
    limit: int = 10,
    min_confidence: float = 60.0,
    current_user: dict = Depends(get_current_user)
):
    """
    Get latest trading signals

    Args:
        limit: Maximum number of signals
        min_confidence: Minimum confidence level

    Returns:
        List of trading signals
    """
    username = current_user["username"]
    scanner = _scanner_instances.get(username)

    if not scanner:
        return []

    signals = scanner.get_latest_signals(limit, min_confidence)
    return signals

@router.get("/signals/{signal_id}", response_model=SignalResponse)
async def get_signal_details(signal_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get detailed information about a specific signal

    Args:
        signal_id: Signal ID

    Returns:
        Detailed signal information
    """
    username = current_user["username"]
    scanner = _scanner_instances.get(username)

    if not scanner:
        raise HTTPException(status_code=404, detail="Scanner não inicializado")

    signal = scanner.get_signal_by_id(signal_id)

    if not signal:
        raise HTTPException(status_code=404, detail="Sinal não encontrado")

    session_manager = get_session_manager()
    client = session_manager.get_client(username)

    if not client:
        raise HTTPException(status_code=400, detail="Usuário não conectado ao IQ Option")

    if not client.is_connected:
        if not await client.connect():
            raise HTTPException(status_code=400, detail=client.last_error or "Não foi possível restabelecer a conexão com a IQ Option")

    candles = await client.get_candles(
        symbol=signal.symbol,
        timeframe=signal.timeframe,
        limit=50
    )

    chart_data = []
    if candles:
        if isinstance(candles, list):
            chart_data = candles
        else:
            chart_data = candles.to_dict(orient="records")

    explanation = _generate_signal_explanation(signal)

    return SignalResponse(
        signal=signal,
        chart_data=chart_data,
        indicators={
            "trend": "bullish" if signal.direction == "CALL" else "bearish",
            "volatility": "moderate"
        },
        explanation=explanation
    )

@router.post("/analyze")
async def analyze_pair(symbol: str, config: ScanConfig, current_user: dict = Depends(get_current_user)):
    """
    Analyze a specific pair using REAL IQ Option data

    Args:
        symbol: Pair symbol (ex: EURUSD, GBPUSD, USDJPY)
        config: Analysis configuration

    Returns:
        Trading signal if found
    """
    session_manager = get_session_manager()
    username = current_user["username"]
    client = session_manager.get_client(username)

    if not client:
        raise HTTPException(status_code=400, detail="Usuário não conectado ao IQ Option")

    if not client.is_connected:
        if not await client.connect():
            raise HTTPException(status_code=400, detail=client.last_error or "Não foi possível restabelecer a conexão com a IQ Option")

    candles = await client.get_candles(
        symbol=symbol,
        timeframe=config.timeframe,
        limit=100
    )

    if not candles or len(candles) < 50:
        raise HTTPException(
            status_code=400,
            detail="Dados insuficientes para análise"
        )

    import pandas as pd
    if isinstance(candles, list):
        df = pd.DataFrame(candles)
    else:
        df = candles.copy()

    signal_gen = SignalGenerator(config)
    signal = signal_gen.generate_signal(symbol, df)

    if not signal:
        return {
            "status": "no_signal",
            "message": "Nenhum sinal detectado no momento"
        }

    return {
        "status": "signal_found",
        "signal": signal
    }

@router.post("/iqoption/connect")
async def connect_iqoption(payload: Dict[str, str] = Body(...), current_user: dict = Depends(get_current_user)):
    """
    Conectar ao IQ Option com credenciais do usuário

    Args:
        email: Email do IQ Option
        password: Senha do IQ Option

    Returns:
        Status da conexão
    """
    try:
        username = current_user["username"]
        session_manager = get_session_manager()

        email = payload.get("email")
        password = payload.get("password")
        account_type = payload.get("account_type")

        if not email or not password:
            raise HTTPException(status_code=400, detail="Informe email e senha do IQ Option")

        print(f"[API] Tentando conectar ao IQ Option com email: {email}")

        connected, message = await session_manager.connect_user(
            username=username,
            email=email,
            password=password,
            account_type=account_type
        )

        if connected:
            print("[API] SUCCESS - Conectado ao IQ Option!")

            client = session_manager.get_client(username)
            pairs = await client.get_available_pairs(include_otc=True) if client else []
            balance_info = await client.get_balance() if client else {"balance": 0, "currency": "USD", "account_type": "UNKNOWN"}

            return {
                "status": "success",
                "message": "Conectado ao IQ Option com sucesso!",
                "connected": True,
                "pairs_count": len(pairs),
                "balance": balance_info.get("balance", 0) if isinstance(balance_info, dict) else balance_info,
                "currency": balance_info.get("currency", "USD") if isinstance(balance_info, dict) else "USD",
                "account_type": session_manager.get_user_account_type(username),
                "data_source": "IQ Option Real API"
            }
        else:
            print(f"[API] ERROR - Falha ao conectar ao IQ Option: {message}")
            return {
                "status": "error",
                "message": message or "Credenciais invalidas ou erro de conexao",
                "connected": False
            }

    except Exception as e:
        print(f"[API] ERROR - Erro ao conectar: {e}")
        return {
            "status": "error",
            "message": f"Erro: {str(e)}",
            "connected": False
        }

@router.get("/iqoption/status")
async def get_iqoption_status(current_user: dict = Depends(get_current_user)):
    """Verificar status da conexão IQ Option"""
    username = current_user["username"]
    session_manager = get_session_manager()
    client = session_manager.get_client(username)

    return {
        "connected": bool(client and client.is_connected),
        "email": client.email if client and client.is_connected else None,
        "account_type": client.account_type if client else session_manager.get_user_account_type(username)
    }

@router.get("/stats", response_model=TradingStats)
async def get_statistics(current_user: dict = Depends(get_current_user)):
    """Get REAL trading statistics from scanner"""
    username = current_user["username"]
    scanner = _scanner_instances.get(username)

    if not scanner:
        return TradingStats(
            total_signals=0,
            win_signals=0,
            loss_signals=0,
            winrate=0.0,
            best_pairs=[],
            average_response_time=0.0
        )

    signals = list(scanner.signal_history)
    total = len(signals)

    symbol_counts = {}
    for sig in signals:
        symbol_counts[sig.symbol] = symbol_counts.get(sig.symbol, 0) + 1

    best_pairs = []
    for symbol, count in sorted(symbol_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
        best_pairs.append({
            "symbol": symbol,
            "winrate": 0.0,
            "signals": count
        })

    return TradingStats(
        total_signals=total,
        win_signals=0,
        loss_signals=0,
        winrate=0.0,
        best_pairs=best_pairs,
        average_response_time=0.0
    )

def _generate_signal_explanation(signal: TradingSignal) -> str:
    """Generate human-readable explanation for a signal"""
    direction_text = "COMPRA (CALL)" if signal.direction == "CALL" else "VENDA (PUT)"

    explanation = f"""
DADOS **Análise Detalhada - {signal.symbol}**

**Direção**: {direction_text}
**Confiança**: {signal.confidence:.1f}%
**Preço de Entrada**: {signal.entry_price:.5f}
**Expiração**: {signal.expiry_minutes} minutos

**Padrão Detectado**: {signal.pattern.description}

**Confluências Confirmadas**:
"""

    for i, conf in enumerate(signal.confluences, 1):
        explanation += f"\n{i}. {conf}"

    if signal.support_resistance:
        explanation += f"\n\n**Nível Chave**: {signal.support_resistance.type.capitalize()} "
        explanation += f"em {signal.support_resistance.level:.5f} "
        explanation += f"(Força: {signal.support_resistance.strength}/5)"

    explanation += f"\n\n⏰ **Sinal gerado em**: {signal.timestamp.strftime('%H:%M:%S')}"

    return explanation

