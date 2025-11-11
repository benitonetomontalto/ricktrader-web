"""IQ Option API Routes"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict
from pydantic import BaseModel

from ..services.iqoption import get_session_manager
from ..services.scanner.iqoption_scanner import IQOptionScanner
from ..core.security import get_current_user_optional
from ..models.schemas import ScanConfig

router = APIRouter(prefix="/iqoption", tags=["IQ Option"])

# Global scanner instances per user
_user_scanners: Dict[str, IQOptionScanner] = {}


# Request/Response Models
class IQOptionLoginRequest(BaseModel):
    email: str
    password: str
    account_type: Optional[str] = "PRACTICE"


class IQOptionLoginResponse(BaseModel):
    success: bool
    message: str
    balance: Optional[float] = None
    account_type: Optional[str] = None
    two_factor_required: bool = False
    two_factor_message: Optional[str] = None


class IQOptionBalanceResponse(BaseModel):
    balance: float
    currency: str = "USD"


class IQOptionPairResponse(BaseModel):
    symbol: str
    name: str
    type: str
    is_active: bool


class IQOptionStatusResponse(BaseModel):
    is_connected: bool
    email: Optional[str] = None
    balance: Optional[float] = None
    account_type: Optional[str] = None
    awaiting_two_factor: bool = False
    two_factor_message: Optional[str] = None


class IQOptionTwoFactorRequest(BaseModel):
    code: str


@router.post("/login", response_model=IQOptionLoginResponse)
async def iqoption_login(
    request: IQOptionLoginRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Connect user to IQ Option

    Args:
        request: IQ Option credentials
        current_user: Current authenticated user (optional)

    Returns:
        Connection status and initial balance
    """
    try:
        # Use email as username if no system auth
        username = request.email if current_user is None else current_user.get("username")
        session_manager = get_session_manager()

        # Connect to IQ Option
        success, message = await session_manager.connect_user(
            username=username,
            email=request.email,
            password=request.password,
            account_type=request.account_type
        )

        client = session_manager.get_client(username)
        two_factor_required = bool(client and getattr(client, "awaiting_two_factor", False))
        if two_factor_required:
            message = (client.two_factor_message if client else None) or message
            return IQOptionLoginResponse(
                success=False,
                message=message,
                balance=None,
                account_type=client.account_type if client else request.account_type,
                two_factor_required=True,
                two_factor_message=client.two_factor_message if client else None
            )

        if not success:
            raise HTTPException(status_code=401, detail=message)

        balance = await session_manager.get_user_balance(username)

        return IQOptionLoginResponse(
            success=True,
            message=message,
            balance=balance,
            account_type=session_manager.get_user_account_type(username)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logout")
async def iqoption_logout(current_user: dict = None, email: str = "default"):
    """Disconnect user from IQ Option"""
    try:
        username = email if current_user is None else current_user.get("username")
        session_manager = get_session_manager()

        success = await session_manager.disconnect_user(username)

        return {"success": success, "message": "Disconnected from IQ Option"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=IQOptionStatusResponse)
async def iqoption_status(current_user: dict = None, email: str = "default"):
    """Get IQ Option connection status"""
    try:
        username = email if current_user is None else current_user.get("username")
        session_manager = get_session_manager()

        client = session_manager.get_client(username)
        if not client:
            return IQOptionStatusResponse(is_connected=False)

        if client.awaiting_two_factor:
            return IQOptionStatusResponse(
                is_connected=False,
                email=client.email,
                account_type=client.account_type,
                awaiting_two_factor=True,
                two_factor_message=client.two_factor_message
            )

        is_connected = session_manager.is_connected(username)
        if not is_connected:
            return IQOptionStatusResponse(is_connected=False)

        balance = await session_manager.get_user_balance(username)

        return IQOptionStatusResponse(
            is_connected=True,
            email=client.email,
            balance=balance,
            account_type=client.account_type
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-2fa", response_model=IQOptionLoginResponse)
async def iqoption_verify_two_factor(
    request: IQOptionTwoFactorRequest,
    current_user: dict = Depends(get_current_user_optional),
    email: str = "default"
):
    """Submit 2FA code to complete IQ Option login"""
    try:
        username = email if current_user is None else current_user.get("username")
        session_manager = get_session_manager()

        success, message = await session_manager.complete_two_factor(username, request.code)
        if not success:
            raise HTTPException(status_code=400, detail=message)

        balance = await session_manager.get_user_balance(username)
        return IQOptionLoginResponse(
            success=True,
            message=message,
            balance=balance,
            account_type=session_manager.get_user_account_type(username),
            two_factor_required=False
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/balance", response_model=IQOptionBalanceResponse)
async def iqoption_balance(current_user: dict = None, email: str = "default"):
    """Get user's IQ Option balance"""
    try:
        username = email if current_user is None else current_user.get("username")
        session_manager = get_session_manager()

        if not session_manager.is_connected(username):
            raise HTTPException(status_code=401, detail="Not connected to IQ Option")

        balance = await session_manager.get_user_balance(username)

        if balance is None:
            raise HTTPException(status_code=500, detail="Failed to get balance")

        return IQOptionBalanceResponse(balance=balance)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/otc-pairs", response_model=List[IQOptionPairResponse])
async def iqoption_otc_pairs(current_user: dict = None, email: str = "default"):
    """Get available OTC pairs from IQ Option"""
    try:
        username = email if current_user is None else current_user.get("username")
        session_manager = get_session_manager()

        if not session_manager.is_connected(username):
            raise HTTPException(status_code=401, detail="Not connected to IQ Option")

        pairs = await session_manager.get_user_pairs(username)

        return [
            IQOptionPairResponse(
                symbol=pair["symbol"],
                name=pair["name"],
                type=pair["type"],
                is_active=pair["is_active"]
            )
            for pair in pairs
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/candles/{symbol}")
async def iqoption_candles(
    symbol: str,
    timeframe: int = 60,
    count: int = 100,
    current_user: dict = None,
    email: str = "default"
):
    """Get candles for a symbol"""
    try:
        username = email if current_user is None else current_user.get("username")
        session_manager = get_session_manager()

        if not session_manager.is_connected(username):
            raise HTTPException(status_code=401, detail="Not connected to IQ Option")

        candles = await session_manager.get_user_candles(
            username=username,
            symbol=symbol,
            timeframe=timeframe,
            count=count
        )

        if candles is None or candles.empty:
            raise HTTPException(status_code=404, detail="No candles found")

        # Convert to dict for JSON response
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "count": len(candles),
            "candles": candles.to_dict(orient="records")
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Scanner Endpoints
@router.post("/scanner/start")
async def start_iqoption_scanner(
    config: ScanConfig,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Start IQ Option scanner for OTC signals"""
    try:
        username = current_user.get("username") if current_user else "default"
        session_manager = get_session_manager()

        # Check if user is connected
        if not session_manager.is_connected(username):
            raise HTTPException(
                status_code=401,
                detail="Not connected to IQ Option. Please login first."
            )

        # Check if scanner already running
        if username in _user_scanners:
            existing_scanner = _user_scanners[username]
            if existing_scanner.is_running:
                raise HTTPException(status_code=400, detail="Scanner already running")
            else:
                # Scanner exists but not running, stop it properly first
                existing_scanner.stop_scanning()

        # Create and start scanner (always create fresh instance for clean state)
        scanner = IQOptionScanner(username=username, config=config)
        _user_scanners[username] = scanner

        # Start scanning in background and store task reference
        import asyncio
        scanner._scan_task = asyncio.create_task(scanner.start_scanning())

        print(f"[START_SCANNER] ========================================")
        print(f"[START_SCANNER] Usuario: {username}")
        print(f"[START_SCANNER] Timeframe: {config.timeframe} minutos")
        print(f"[START_SCANNER] Sensitivity: {config.sensitivity}")
        print(f"[START_SCANNER] Only OTC: {config.only_otc}")
        print(f"[START_SCANNER] Only Open Market: {config.only_open_market}")
        print(f"[START_SCANNER] Symbols: {config.symbols}")
        print(f"[START_SCANNER] Nova task criada: {scanner._scan_task}")
        print(f"[START_SCANNER] ========================================")

        return {
            "success": True,
            "message": "IQ Option scanner started",
            "config": {
                "timeframe": config.timeframe,
                "sensitivity": config.sensitivity
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scanner/stop")
async def stop_iqoption_scanner(current_user: Optional[dict] = Depends(get_current_user_optional)):
    """Stop IQ Option scanner"""
    try:
        username = current_user.get("username") if current_user else "default"

        if username not in _user_scanners:
            raise HTTPException(status_code=400, detail="No scanner running")

        scanner = _user_scanners[username]
        scanner.stop_scanning()

        # Wait a bit for the task to actually cancel
        import asyncio
        if scanner._scan_task and not scanner._scan_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(scanner._scan_task), timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                # Expected - task was cancelled
                pass

        print(f"[STOP_SCANNER] Scanner parado para {username}")

        return {"success": True, "message": "Scanner stopped"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scanner/status")
async def iqoption_scanner_status(current_user: Optional[dict] = Depends(get_current_user_optional)):
    """Get IQ Option scanner status"""
    try:
        username = current_user.get("username") if current_user else "default"

        if username not in _user_scanners:
            return {
                "is_running": False,
                "signals_generated": 0
            }

        scanner = _user_scanners[username]
        return scanner.get_status()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scanner/signals")
async def iqoption_scanner_signals(current_user: Optional[dict] = Depends(get_current_user_optional)):
    """Get latest signals from IQ Option scanner"""
    try:
        username = current_user.get("username") if current_user else "default"

        if username not in _user_scanners:
            return []

        scanner = _user_scanners[username]
        signals = scanner.get_latest_signals()

        return signals

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
