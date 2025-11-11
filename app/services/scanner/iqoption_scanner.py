"""IQ Option Scanner - Scans OTC pairs using IQ Option data"""
import asyncio
from typing import List, Optional, Dict
from datetime import datetime
import pandas as pd

from ...models.schemas import ScanConfig, TradingSignal
from ..iqoption import get_session_manager
from .signal_generator import SignalGenerator


class IQOptionScanner:
    """Scanner that uses IQ Option data for signal generation"""

    def __init__(self, username: str, config: ScanConfig):
        """
        Initialize IQ Option scanner

        Args:
            username: User to get IQ Option connection for
            config: Scanner configuration
        """
        self.username = username
        self.config = config
        self.signal_generator = SignalGenerator(config)
        self.is_running = False
        self.latest_signals: Dict[str, TradingSignal] = {}
        self.session_manager = get_session_manager()
        self._scan_task: Optional[asyncio.Task] = None
        # CRITICAL: Limit concurrent requests to prevent memory explosion
        self._semaphore = asyncio.Semaphore(5)  # Max 5 concurrent pair scans
        self._scan_interval = 30  # Scan every 30 seconds (more stable)

    async def start_scanning(self):
        """Start scanning IQ Option OTC pairs"""
        self.is_running = True

        print(f"[IQOptionScanner] ========================================")
        print(f"[IQOptionScanner] INICIANDO SCAN")
        print(f"[IQOptionScanner] Usuario: {self.username}")
        print(f"[IQOptionScanner] Timeframe configurado: {self.config.timeframe} minutos")
        print(f"[IQOptionScanner] Timeframe em segundos: {self.config.timeframe * 60}")
        print(f"[IQOptionScanner] ========================================")

        # Check if user is connected
        is_connected = self.session_manager.is_connected(self.username)
        print(f"[IQOptionScanner] Verificando conexao: is_connected={is_connected}")

        if not is_connected:
            print(f"[IQOptionScanner] ERRO: Usuario {self.username} nao conectado ao IQ Option")
            print(f"[IQOptionScanner] Scanner nao pode iniciar sem conexao ativa")
            self.is_running = False
            return

        # Refresh session timeout
        client = self.session_manager.get_client(self.username)
        if client:
            print(f"[IQOptionScanner] Conexao OK - Cliente ativo: {client.is_connected}")
            print(f"[IQOptionScanner] Timeout da sessao atualizado")
        else:
            print(f"[IQOptionScanner] AVISO: Cliente nao encontrado no session_manager")
            self.is_running = False
            return

        # Get OTC pairs
        pairs = await self._get_otc_pairs()

        if not pairs:
            print("[IQOptionScanner] Nenhum par OTC disponivel")
            self.is_running = False
            return

        print(f"[IQOptionScanner] Iniciando scan em {len(pairs)} pares OTC com timeframe {self.config.timeframe}min...")

        while self.is_running:
            try:
                # Verify connection is still active before scanning
                if not self.session_manager.is_connected(self.username):
                    print(f"[IQOptionScanner] ERRO: Conexao perdida durante scan!")
                    print(f"[IQOptionScanner] Parando scanner - reconecte e tente novamente")
                    self.is_running = False
                    break

                # Scan all OTC pairs with controlled concurrency
                # CRITICAL FIX: Process pairs in batches to prevent memory explosion
                new_signals = []
                for pair in pairs:
                    if not self.is_running:
                        break

                    async with self._semaphore:
                        try:
                            # Add timeout to prevent hanging requests
                            result = await asyncio.wait_for(
                                self._scan_pair(pair),
                                timeout=10.0  # 10 second timeout per pair
                            )
                            if isinstance(result, TradingSignal):
                                new_signals.append(result)
                                self.latest_signals[result.symbol] = result
                        except asyncio.TimeoutError:
                            print(f"[IQOptionScanner] Timeout ao escanear {pair.get('symbol', '?')}")
                        except Exception as e:
                            print(f"[IQOptionScanner] Erro ao escanear {pair.get('symbol', '?')}: {e}")

                # Log new signals
                if new_signals:
                    print(f"[IQOptionScanner] {len(new_signals)} novos sinais OTC!")
                    for signal in new_signals:
                        print(f"  - {signal.symbol}: {signal.direction} "
                              f"({signal.confidence:.1f}% confianca)")

                # Wait before next scan (increased for stability)
                await asyncio.sleep(self._scan_interval)

            except asyncio.CancelledError:
                print(f"[IQOptionScanner] Scan cancelado via stop_scanning()")
                break
            except Exception as e:
                print(f"[IQOptionScanner] Erro durante scan: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(5)

    def stop_scanning(self):
        """Stop scanning and clean up state"""
        self.is_running = False

        # Cancel the scanning task if it exists
        if self._scan_task and not self._scan_task.done():
            self._scan_task.cancel()
            print("[IQOptionScanner] Task de scan cancelada")

        # Clear latest signals to ensure fresh start on resume
        self.latest_signals.clear()

        print("[IQOptionScanner] Scan interrompido e estado limpo")

    async def _get_otc_pairs(self) -> List[Dict]:
        """Get available pairs from IQ Option honoring scanner config"""
        try:
            pairs = await self.session_manager.get_user_pairs(self.username)

            # Filter only active pairs
            active_pairs = [p for p in pairs if p.get("is_active", False)]

            # Respect scanner configuration filters
            if self.config.only_otc:
                active_pairs = [p for p in active_pairs if p.get("is_otc", False)]
            elif self.config.only_open_market:
                active_pairs = [p for p in active_pairs if not p.get("is_otc", False)]

            if self.config.symbols:
                symbols_set = {symbol.upper() for symbol in self.config.symbols}
                active_pairs = [
                    p for p in active_pairs
                    if p.get("symbol", "").upper() in symbols_set
                ]

            return active_pairs

        except Exception as e:
            print(f"[IQOptionScanner] Erro ao buscar pares OTC: {e}")
            return []

    async def _scan_pair(self, pair: Dict) -> Optional[TradingSignal]:
        """
        Scan a single OTC pair for signals

        Args:
            pair: Trading pair info

        Returns:
            Trading signal if found
        """
        try:
            symbol = pair["symbol"]

            # Get candles from IQ Option
            # Convert timeframe from minutes to seconds for IQ Option
            timeframe_seconds = self.config.timeframe * 60

            print(f"[IQOptionScanner] Buscando candles para {symbol}: timeframe={self.config.timeframe}min ({timeframe_seconds}s)")

            candles = await self.session_manager.get_user_candles(
                username=self.username,
                symbol=symbol,
                timeframe=timeframe_seconds,
                count=100  # Get 100 candles for analysis
            )

            if candles is None or candles.empty:
                print(f"[IQOptionScanner] Nenhum candle retornado para {symbol}")
                return None

            # Ensure we have a DataFrame for the generator
            if not isinstance(candles, pd.DataFrame):
                candles = pd.DataFrame(candles)

            # Generate signal using signal generator (synchronous)
            signal = self.signal_generator.generate_signal(symbol, candles)

            return signal

        except Exception as e:
            print(f"[IQOptionScanner] Erro ao analisar {pair.get('symbol', '?')}: {e}")
            return None

    def get_latest_signals(self) -> List[TradingSignal]:
        """Get latest signals from all pairs"""
        return list(self.latest_signals.values())

    def get_status(self) -> dict:
        """Get scanner status"""
        return {
            "is_running": self.is_running,
            "username": self.username,
            "active_pairs": list(self.latest_signals.keys()),
            "signals_generated": len(self.latest_signals),
            "config": {
                "timeframe": self.config.timeframe,
                "sensitivity": self.config.sensitivity,
            }
        }
