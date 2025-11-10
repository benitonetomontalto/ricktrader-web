"""
IQ Option Real-Time Data Client
Connects to IQ Option API for real market data
"""
import time
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
import os
import json
from dotenv import load_dotenv

try:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from iqoptionapi.stable_api import IQ_Option
    IQ_OPTION_AVAILABLE = True
except ImportError as e:
    IQ_OPTION_AVAILABLE = False
    print(f"[WARNING] IQ Option API not available: {e}")
    print("[INFO] Please check the iqoptionapi folder exists in app/services/")


load_dotenv()


class IQOptionClient:
    """Client for fetching real-time data from IQ Option"""

    def __init__(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        account_type: Optional[str] = None
    ):
        self.api: Optional[IQ_Option] = None
        self.connected = False
        self.email = email or os.getenv("IQOPTION_EMAIL")
        self.password = password or os.getenv("IQOPTION_PASSWORD")
        self.account_type = self._normalize_account_type(
            account_type or os.getenv("IQOPTION_ACCOUNT_TYPE", "PRACTICE")
        )
        self.last_error: Optional[str] = None
        self._connected_email: Optional[str] = None
        self._connected_password: Optional[str] = None
        self._connected_account_type: Optional[str] = None
        self._last_known_balance: Optional[float] = None
        self.awaiting_two_factor: bool = False
        self.two_factor_message: Optional[str] = None
        self.two_factor_started_at: Optional[datetime] = None

        if not self.email or not self.password:
            print("[ERROR] IQ Option credentials not found in .env file")
            print("Please add IQOPTION_EMAIL and IQOPTION_PASSWORD to your .env file")

    @property
    def is_connected(self) -> bool:
        """Return current connection state"""
        return self.connected

    def set_credentials(self, email: str, password: str):
        """Update account credentials used for the connection"""
        self.email = email
        self.password = password

    def set_account_type(self, account_type: str):
        """Update account type (PRACTICE or REAL)"""
        self.account_type = self._normalize_account_type(account_type)

    async def connect(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        account_type: Optional[str] = None
    ) -> bool:
        """Connect to IQ Option API"""
        if not IQ_OPTION_AVAILABLE:
            error_msg = "[ERRO CRITICO] Biblioteca IQ Option nao disponivel no executavel! Validacao de credenciais DESABILITADA!"
            print(error_msg)
            self.last_error = "Biblioteca IQ Option nao encontrada. Reinstale a aplicacao."
            return False

        if email:
            self.email = email
        if password:
            self.password = password

        previous_account = self.account_type
        if account_type:
            self.set_account_type(account_type)

        loop = asyncio.get_event_loop()
        self.awaiting_two_factor = False
        self.two_factor_message = None
        self.two_factor_started_at = None

        credentials_changed = (
            self._connected_email is not None
            and (self.email != self._connected_email or self.password != self._connected_password)
        )
        account_changed = previous_account != self.account_type

        if self.connected and self.api:
            if credentials_changed:
                print("[IQ Option] Credentials changed - reconnecting")
                await self.disconnect()
            else:
                if account_changed:
                    await loop.run_in_executor(
                        None,
                        lambda: self.api.change_balance(self.account_type)
                    )
                    print(f"[IQ Option] Account switched to {self.account_type}")
                return True

        if not self.email or not self.password:
            print("[ERROR] Missing IQ Option credentials")
            self.last_error = "Missing credentials"
            return False

        try:
            self.api = await loop.run_in_executor(
                None,
                lambda: IQ_Option(self.email, self.password, self.account_type)
            )

            check, reason = await loop.run_in_executor(None, self.api.connect)

            if not check:
                if self._is_two_factor_challenge(reason):
                    self._handle_two_factor_challenge(reason)
                    self.last_error = self.two_factor_message
                    print(f"[IQ Option] 2FA required: {self.two_factor_message}")
                    return False

                print(f"[IQ Option] Raw failure reason: {repr(reason)}")
                error_message = self._interpret_reason(reason)
                print(f"[IQ Option] Connection failed: {error_message}")
                self.last_error = error_message
                self._clear_connection_state()
                return False

            await self._finalize_successful_login()
            return True

        except Exception as exc:
            print(f"[IQ Option] Connection exception raw: {repr(exc)}")
            error_message = self._interpret_exception(exc)
            print(f"[IQ Option] Connection error: {error_message}")
            self.last_error = error_message
            self._clear_connection_state()
            return False

    async def submit_two_factor_code(self, code: str) -> tuple[bool, str]:
        """Submit a verification code to finish the IQ Option login."""
        if not self.awaiting_two_factor or not self.api:
            return False, "Nenhum desafio de verificacao pendente."

        loop = asyncio.get_event_loop()
        try:
            check, reason = await loop.run_in_executor(
                None,
                lambda: self.api.connect_2fa(code)
            )
        except Exception as exc:
            message = f"Erro ao validar codigo: {exc}"
            print(f"[IQ Option] 2FA exception: {exc}")
            self.last_error = message
            return False, message

        if not check:
            if self._is_two_factor_challenge(reason):
                self._handle_two_factor_challenge(reason)
                message = self.two_factor_message or "Codigo invalido. Tente novamente."
            else:
                message = self._interpret_reason(reason)
                self._clear_connection_state()
            self.last_error = message
            print(f"[IQ Option] 2FA verification failed: {message}")
            return False, message

        await self._finalize_successful_login()
        success_message = f"Verificacao concluida! Conta {self.account_type}"
        print(f"[IQ Option] 2FA complete: {success_message}")
        return True, success_message

    async def connect_with_credentials(
        self,
        email: str,
        password: str,
        account_type: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Helper that sets credentials before attempting to connect.

        Returns:
            Tuple (success, message)
        """
        self.set_credentials(email, password)
        if account_type:
            self.set_account_type(account_type)
        success = await self.connect()
        if success:
            return True, f"Conectado ao IQ Option com sucesso! Conta: {self.account_type}"
        return False, self.last_error or "Falha ao conectar ao IQ Option"

    async def check_connection(self) -> bool:
        """Verify if connection is still alive"""
        if not self.api or not self.connected:
            return False

        try:
            loop = asyncio.get_event_loop()
            checker = getattr(self.api, "check_connect", None)
            if callable(checker):
                is_ok = await loop.run_in_executor(None, checker)
            else:
                balance_info = await self.get_balance()
                is_ok = isinstance(balance_info, dict)

            self.connected = bool(is_ok)
            if not self.connected:
                self.last_error = "Sessao desconectada"

            return self.connected
        except Exception as exc:
            print(f"[IQ Option] Connection check error: {exc}")
            self.connected = False
            self.last_error = str(exc)
            return False

    async def get_balance(self) -> Dict:
        """Get account balance from IQ Option"""
        if not self.connected or not self.api:
            return {
                "balance": self._last_known_balance or 0,
                "currency": "USD",
                "account_type": self.account_type,
            }

        try:
            loop = asyncio.get_event_loop()

            balance = await loop.run_in_executor(None, self.api.get_balance)
            self._last_known_balance = float(balance)

            # Try to get balance_type, fallback to self.account_type if not available
            balance_type = None
            try:
                balance_type = await loop.run_in_executor(
                    None,
                    lambda: getattr(self.api, 'balance_type', None)
                )
            except Exception:
                pass

            return {
                "balance": round(float(balance), 2),
                "currency": "USD",
                "account_type": self._normalize_account_type(balance_type or self.account_type),
            }
        except Exception as exc:
            print(f"[IQ Option] Error getting balance: {exc}")
            return {
                "balance": self._last_known_balance or 0,
                "currency": "USD",
                "account_type": self.account_type,
            }

    async def disconnect(self):
        """Disconnect from IQ Option"""
        try:
            if self.api and self.connected:
                loop = asyncio.get_event_loop()
                # Try different disconnect methods
                if hasattr(self.api, 'close'):
                    await loop.run_in_executor(None, self.api.close)
                elif hasattr(self.api, 'disconnect'):
                    await loop.run_in_executor(None, self.api.disconnect)
                print("[IQ Option] Disconnected")
        except Exception as exc:
            print(f"[IQ Option] Disconnect error: {exc}")
        finally:
            self._clear_connection_state()

    def _clear_connection_state(self):
        """Reset cached connection data"""
        self.api = None
        self.connected = False
        self._connected_email = None
        self._connected_password = None
        self._connected_account_type = None
        self._last_known_balance = None
        self.awaiting_two_factor = False
        self.two_factor_message = None
        self.two_factor_started_at = None

    def _convert_timeframe_to_seconds(self, timeframe_minutes: int) -> int:
        """Convert timeframe in minutes to seconds"""
        return timeframe_minutes * 60

    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol format for IQ Option.
        EURUSD, GBPUSD, etc. stay the same.
        OTC symbols might need -OTC suffix.
        """
        if symbol.endswith("-OTC"):
            return symbol
        return symbol

    def _normalize_account_type(self, account_type: Optional[str]) -> str:
        """Normalize account type text"""
        if not account_type:
            return "PRACTICE"
        normalized = account_type.strip().upper()
        if normalized not in {"PRACTICE", "REAL"}:
            return "PRACTICE"
        return normalized

    def _interpret_reason(self, reason: Optional[object]) -> str:
        """Convert IQ Option error reason into user-friendly message"""
        if not reason:
            return "Falha ao conectar ao IQ Option. Verifique suas credenciais."

        if isinstance(reason, dict):
            message = reason.get("message") or reason.get("detail")
            if message:
                return message
            return json.dumps(reason)

        text = str(reason)
        if "Expecting value" in text:
            return (
                "A IQ Option retornou uma resposta inesperada. "
                "Verifique se o login esta correto e se a conta nao requer verificacao adicional."
            )

        if "401" in text or "unauthorized" in text.lower():
            return "Credenciais invalidas ou acesso nao autorizado no IQ Option."

        return text

    def _interpret_exception(self, exc: Exception) -> str:
        """Convert raw exception into clearer text"""
        if isinstance(exc, json.JSONDecodeError):
            return (
                "Resposta invalida recebida da IQ Option. "
                "Possivel 2FA/captcha pendente ou instabilidade no servico."
            )
        return self._interpret_reason(str(exc))

    def _is_two_factor_challenge(self, reason: Optional[object]) -> bool:
        """Detect if IQ Option is asking for additional verification."""
        if not reason:
            return False
        if isinstance(reason, str) and "2FA" in reason.upper():
            return True

        payload = self._parse_reason_payload(reason)
        if isinstance(payload, dict):
            code_value = str(payload.get("code", "")).lower()
            return code_value in {"verify", "2fa", "sms", "email"}

        return False

    def _parse_reason_payload(self, reason: object) -> Optional[dict]:
        """Attempt to parse a reason payload as JSON."""
        if isinstance(reason, dict):
            return reason
        try:
            return json.loads(reason)
        except Exception:
            return None

    def _handle_two_factor_challenge(self, reason: Optional[object]):
        """Mark client state as waiting for a verification code."""
        self.awaiting_two_factor = True
        payload = self._parse_reason_payload(reason) or {}
        method = (payload.get("method") or payload.get("type") or "sms").upper()
        self.two_factor_started_at = datetime.utcnow()
        base_message = (
            "Codigo de verificacao enviado pela IQ Option. "
            "Digite o codigo recebido para concluir o login."
        )
        if method:
            self.two_factor_message = (
                f"Verificacao {method} pendente. "
                "Informe o codigo recebido da IQ Option."
            )
        else:
            self.two_factor_message = base_message

    async def _finalize_successful_login(self):
        """Finalize the session after authentication succeeds."""
        if not self.api:
            raise RuntimeError("Cliente IQ Option indisponivel apos login.")

        loop = asyncio.get_event_loop()
        self.connected = True
        self.awaiting_two_factor = False
        self.two_factor_message = None
        self.two_factor_started_at = None
        self.last_error = None
        print("[IQ Option] Connected successfully!")

        await loop.run_in_executor(
            None,
            lambda: self.api.change_balance(self.account_type)
        )
        print(f"[IQ Option] Using {self.account_type} account")

        checker = getattr(self.api, "check_connect", None)
        if callable(checker):
            is_alive = await loop.run_in_executor(None, checker)
            if not is_alive:
                self.last_error = "IQ Option disconnected right after login."
                print("[IQ Option] Connection validation failed immediately after login")
                await self.disconnect()
                raise RuntimeError(self.last_error)

        try:
            balance_value = await loop.run_in_executor(None, self.api.get_balance)
            if balance_value is None:
                raise RuntimeError("Falha ao obter saldo. Credenciais podem estar incorretas.")

            self._last_known_balance = float(balance_value)
            if self._last_known_balance < 0:
                raise RuntimeError("Saldo invalido retornado. Credenciais podem estar incorretas.")

            print(f"[IQ Option] [OK] VALIDACAO PASSOU: Saldo obtido com sucesso: ${self._last_known_balance:.2f}")
        except Exception as balance_error:
            self.last_error = (
                "Falha ao validar credenciais. "
                "Verifique se o email e senha estao corretos."
            )
            print(f"[IQ Option] VALIDACAO FALHOU: Erro ao buscar saldo: {balance_error}")
            await self.disconnect()
            raise

        self._connected_email = self.email
        self._connected_password = self.password
        self._connected_account_type = self.account_type

    async def get_candles(
        self,
        symbol: str,
        timeframe: int = 1,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get real-time candles from IQ Option

        Args:
            symbol: Trading pair (e.g., 'EURUSD', 'GBPUSD')
            timeframe: Timeframe in minutes (1, 5, 15, 30, 60)
            limit: Number of candles to fetch

        Returns:
            List of candle dictionaries with OHLCV data
        """
        if not self.connected or not self.api:
            print("[IQ Option] Not connected. Attempting to connect...")
            connected = await self.connect()
            if not connected:
                raise Exception("Failed to connect to IQ Option")

        try:
            normalized_symbol = self._normalize_symbol(symbol)
            timeframe_seconds = self._convert_timeframe_to_seconds(timeframe)
            end_time = int(time.time())

            loop = asyncio.get_event_loop()
            candles = await loop.run_in_executor(
                None,
                lambda: self.api.get_candles(
                    normalized_symbol,
                    timeframe_seconds,
                    limit,
                    end_time
                )
            )

            if not candles:
                print(f"[IQ Option] No candles returned for {normalized_symbol}")
                return []

            formatted_candles = []
            for candle in candles:
                formatted_candles.append({
                    "timestamp": datetime.fromtimestamp(candle["from"]),
                    "open": float(candle["open"]),
                    "high": float(candle["max"]),
                    "low": float(candle["min"]),
                    "close": float(candle["close"]),
                    "volume": float(candle.get("volume", 0)),
                })

            print(f"[IQ Option] Fetched {len(formatted_candles)} candles for {normalized_symbol} ({timeframe}M)")
            return formatted_candles

        except Exception as exc:
            print(f"[IQ Option] Error fetching candles for {symbol}: {exc}")
            raise

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol"""
        if not self.connected or not self.api:
            await self.connect()

        try:
            normalized_symbol = self._normalize_symbol(symbol)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.api.start_candles_stream(normalized_symbol, 60)
            )

            await asyncio.sleep(0.5)

            candles = await loop.run_in_executor(
                None,
                lambda: self.api.get_realtime_candles(normalized_symbol, 60)
            )

            if candles:
                latest = list(candles.values())[-1] if isinstance(candles, dict) else candles[-1]
                return float(latest.get("close", latest.get("open", 0)))

            return None

        except Exception as exc:
            print(f"[IQ Option] Error getting current price for {symbol}: {exc}")
            return None

    async def get_available_pairs(self, include_otc: bool = True) -> List[Dict]:
        """
        Get list of available trading pairs from IQ Option

        Returns:
            List of dictionaries with pair information
        """
        if not self.connected or not self.api:
            await self.connect()

        try:
            loop = asyncio.get_event_loop()
            assets = await loop.run_in_executor(
                None,
                lambda: self.api.get_all_open_time()
            )

            pairs = []
            seen_symbols = set()
            market_map = {
                "binary": "BINARY",
                "turbo": "TURBO",
                "digital": "DIGITAL",
            }

            if assets:
                for market_key, market_label in market_map.items():
                    market_assets = assets.get(market_key, {})
                    for asset_name, asset_data in market_assets.items():
                        symbol_key = f"{asset_name}:{market_label}"
                        if symbol_key in seen_symbols:
                            continue

                        is_open = asset_data.get("open", False)
                        is_otc = "-OTC" in asset_name or "OTC" in asset_name

                        if not include_otc and is_otc:
                            continue

                        pairs.append({
                            "symbol": asset_name,
                            "name": asset_name.replace("-OTC", "").replace("_", "/"),
                            "is_otc": is_otc,
                            "is_active": is_open,
                            "type": market_label,
                        })
                        seen_symbols.add(symbol_key)

            print(f"[IQ Option] Found {len(pairs)} available pairs")
            return pairs

        except Exception as exc:
            print(f"[IQ Option] Error getting available pairs: {exc}")
            return self._get_default_pairs()

    def _get_default_pairs(self) -> List[Dict]:
        """Return default FOREX pairs as fallback"""
        default_pairs = [
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD",
            "EURJPY", "GBPJPY", "EURGBP", "AUDJPY", "EURAUD", "USDCHF",
            "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "AUDUSD-OTC",
        ]

        return [
            {
                "symbol": symbol,
                "name": symbol.replace("-OTC", "").replace("_", "/"),
                "is_otc": "-OTC" in symbol,
                "is_active": True,
                "type": "OTC" if "-OTC" in symbol else "BINARY",
            }
            for symbol in default_pairs
        ]


# Global client instance
iq_client = IQOptionClient()


async def get_iq_candles(symbol: str, timeframe: int = 1, limit: int = 100) -> List[Dict]:
    """Convenience function to get candles"""
    return await iq_client.get_candles(symbol, timeframe, limit)


async def get_iq_current_price(symbol: str) -> Optional[float]:
    """Convenience function to get current price"""
    return await iq_client.get_current_price(symbol)
