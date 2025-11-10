"""
Automatic Multi-Pair Scanner
Scans multiple pairs simultaneously for trading opportunities
NOW USING REAL MARKET DATA FROM BINANCE!
"""
import asyncio
from typing import List, Optional, Dict, Union
from datetime import datetime, timedelta
from ...models.schemas import ScanConfig, TradingSignal
from .mboption_client import MBOptionClient
from .market_data_client import RealMarketDataClient
from .iqoption_client import IQOptionClient
from .signal_generator import SignalGenerator
from ...websocket.signal_websocket import ws_manager


class AutoScanner:
    """Automatically scan multiple pairs for trading signals"""

    def __init__(
        self,
        client: Union[MBOptionClient, RealMarketDataClient, IQOptionClient],
        config: ScanConfig
    ):
        """
        Initialize auto scanner

        Args:
            client: MB Option client
            config: Scan configuration
        """
        self.client = client
        self.config = config
        self.signal_generator = SignalGenerator(config)
        self.is_running = False
        self.latest_signals: Dict[str, TradingSignal] = {}  # ultimo por simbolo
        self.signal_history: List[TradingSignal] = []
        self.signal_index: Dict[str, TradingSignal] = {}

    async def start_scanning(self):
        """Start the scanning process"""
        self.is_running = True

        while self.is_running:
            try:
                pairs = await self._get_pairs_to_scan()
                if not pairs:
                    print('[AutoScanner] Nenhuma paridade disponivel para o modo atual.')
                    await asyncio.sleep(8)
                    continue

                print(f"[AutoScanner] Varredura em {len(pairs)} paridades...")

                tasks = [self._scan_pair(pair) for pair in pairs]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                new_signals = []
                for result in results:
                    if isinstance(result, TradingSignal):
                        new_signals.append(result)

                # Log new signals and broadcast via WebSocket
                if new_signals:
                    print(f"[AutoScanner] {len(new_signals)} novos sinais detectados!")
                    for signal in new_signals:
                        print(f"  - {signal.symbol}: {signal.direction} "
                              f"({signal.confidence:.1f}% confianca)")
                        self.latest_signals[signal.symbol] = signal
                        self.signal_history.append(signal)
                        self.signal_index[signal.signal_id] = signal
                        if len(self.signal_history) > 200:
                            oldest = self.signal_history.pop(0)
                            self.signal_index.pop(oldest.signal_id, None)
                            if self.latest_signals.get(oldest.symbol) == oldest:
                                self.latest_signals.pop(oldest.symbol, None)

                        await ws_manager.broadcast_signal(signal.dict())

                # Wait before next scan cycle - REDUZIDO para gerar mais sinais
                # Modo agressivo: 2 segundos, outros: 4 segundos
                await asyncio.sleep(2 if self.config.sensitivity == "aggressive" else 4)

            except Exception as e:
                print(f"[AutoScanner] Erro durante scan: {e}")
                await asyncio.sleep(5)

    def stop_scanning(self):
        """Stop the scanning process"""
        self.is_running = False
        print("[AutoScanner] Scan interrompido.")

    async def _get_pairs_to_scan(self) -> List[dict]:
        """Get list of pairs to scan based on configuration"""

        if self.config.mode == "manual" and self.config.symbols:
            all_pairs = await self.client.get_available_pairs(include_otc=True)
            return [p for p in all_pairs if p['symbol'] in self.config.symbols]

        include_otc_flag = not self.config.only_open_market
        pairs = await self.client.get_available_pairs(include_otc=include_otc_flag)

        # LOG: Pares obtidos antes do filtro
        print(f"[AutoScanner] Pares disponíveis ANTES do filtro: {len(pairs)}")

        if self.config.only_otc:
            pairs = [p for p in pairs if p['is_otc']]
            print(f"[AutoScanner] Filtro OTC aplicado: {len(pairs)} pares OTC")
        elif self.config.only_open_market:
            pairs = [p for p in pairs if not p['is_otc']]
            print(f"[AutoScanner] Filtro MERCADO ABERTO aplicado: {len(pairs)} pares")
        else:
            print(f"[AutoScanner] SEM FILTRO de mercado: {len(pairs)} pares (OTC + Aberto)")

        # Aumentar para 30 pares para compensar os que falham
        max_pairs = 30
        if hasattr(self.config, 'MAX_CONCURRENT_PAIRS'):
            max_pairs = self.config.MAX_CONCURRENT_PAIRS

        limit = pairs[:max_pairs]

        print(f"[AutoScanner] Total de pares que serão analisados: {len(limit)}")
        return limit

    async def _scan_pair(self, pair: dict) -> Optional[TradingSignal]:
        """
        Scan a single pair for trading signals

        Args:
            pair: Trading pair information

        Returns:
            TradingSignal if found, None otherwise
        """
        try:
            symbol = pair['symbol']

            # Get candlestick data
            data = await self.client.get_candles(
                symbol=symbol,
                timeframe=self.config.timeframe,
                limit=100
            )

            # Reduzir requisito mínimo para gerar mais sinais
            min_needed = 20 if self.config.sensitivity == "aggressive" else 30
            if data is None or len(data) < min_needed:
                return None

            # Convert to DataFrame if needed (IQ Option returns list of dicts)
            if isinstance(data, list):
                import pandas as pd
                df = pd.DataFrame(data)
            else:
                df = data

            # Generate signal
            signal = self.signal_generator.generate_signal(symbol, df)

            # Check if this is a new signal (not duplicate)
            if signal:
                # Check if we already have a recent signal for this symbol
                if symbol in self.latest_signals:
                    prev_signal = self.latest_signals[symbol]
                    time_diff = (signal.timestamp - prev_signal.timestamp).total_seconds()

                    # Ignore duplicates only se IDÊNTICO (15 segundos + mesma direção)
                    if time_diff < 15 and signal.direction == prev_signal.direction:
                        return None

            return signal

        except Exception as e:
            print(f"[AutoScanner] Erro ao escanear {pair['symbol']}: {e}")
            return None

    def get_latest_signals(
        self,
        limit: int = 10,
        min_confidence: float = 60.0
    ) -> List[TradingSignal]:
        """
        Get latest signals

        Args:
            limit: Maximum number of signals to return
            min_confidence: Minimum confidence level

        Returns:
            List of trading signals
        """
        signals = [s for s in reversed(self.signal_history) if s.confidence >= min_confidence]
        return signals[:limit]

    def get_signal_by_id(self, signal_id: str) -> Optional[TradingSignal]:
        """Get a specific signal by ID"""
        return self.signal_index.get(signal_id)

    def clear_old_signals(self, max_age_minutes: int = 30):
        """Remove signals older than specified minutes"""
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)

        initial_count = len(self.signal_history)
        self.signal_history = [s for s in self.signal_history if s.timestamp >= cutoff]
        self.signal_index = {s.signal_id: s for s in self.signal_history}

        self.latest_signals = {}
        for sig in self.signal_history:
            prev = self.latest_signals.get(sig.symbol)
            if not prev or sig.timestamp > prev.timestamp:
                self.latest_signals[sig.symbol] = sig

        removed = initial_count - len(self.signal_history)
        if removed > 0:
            print(f"[AutoScanner] Removidos {removed} sinais antigos.")



