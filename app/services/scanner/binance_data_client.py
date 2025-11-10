"""
Binance Data Client - DADOS REAIS SEM LIMITE
Fornece dados de criptomoedas em tempo real da Binance
"""
import asyncio
import aiohttp
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import time


class BinanceDataClient:
    """Client para dados REAIS da Binance - SEM LIMITE DE REQUISICOES"""

    def __init__(self):
        """Initialize Binance Data client"""
        self.base_url = "https://api.binance.com/api/v3"
        self.session: Optional[aiohttp.ClientSession] = None

        # Pares de trading disponiveis (criptomoedas)
        self.trading_pairs = [
            # Principais pares USDT (equivalentes a OTC em volume)
            "BTCUSDT",   # Bitcoin/USDT
            "ETHUSDT",   # Ethereum/USDT
            "BNBUSDT",   # Binance Coin/USDT
            "XRPUSDT",   # Ripple/USDT
            "ADAUSDT",   # Cardano/USDT
            "DOGEUSDT",  # Dogecoin/USDT
            "SOLUSDT",   # Solana/USDT
            "DOTUSDT",   # Polkadot/USDT
            "MATICUSDT", # Polygon/USDT
            "LTCUSDT",   # Litecoin/USDT
            "AVAXUSDT",  # Avalanche/USDT
            "LINKUSDT",  # Chainlink/USDT
        ]

        # Mapeamento de timeframes (minutos -> Binance interval)
        self.timeframe_map = {
            1: "1m",
            3: "3m",
            5: "5m",
            15: "15m",
            30: "30m",
            60: "1h",
            240: "4h",
            1440: "1d"
        }

    async def connect(self):
        """Estabelecer conexao com Binance API"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        # Testar conexao
        try:
            async with self.session.get(f"{self.base_url}/ping") as response:
                if response.status == 200:
                    print("[BINANCE] OK Conectado a Binance API (DADOS REAIS)")
                    print(f"[BINANCE] {len(self.trading_pairs)} pares de cripto disponiveis")
                    print("[BINANCE] SEM LIMITE de requisicoes!")
                    return True
        except Exception as e:
            print(f"[BINANCE] ERRO ao conectar: {e}")
            return False

    async def disconnect(self):
        """Desconectar"""
        if self.session:
            await self.session.close()
            self.session = None

    async def get_available_pairs(self, include_otc: bool = True) -> List[Dict]:
        """
        Obter lista de pares disponiveis

        Returns:
            Lista de pares REAIS da Binance
        """
        pairs = []

        for symbol in self.trading_pairs:
            # Extrair base e quote
            base = symbol.replace("USDT", "")

            pairs.append({
                "symbol": symbol,
                "name": f"{base}/USDT",
                "is_otc": False,  # Cripto opera 24/7
                "is_active": True,
                "exchange": "Binance"
            })

        return pairs

    async def get_candles(
        self,
        symbol: str,
        timeframe: int = 1,
        count: int = 100
    ) -> Optional[pd.DataFrame]:
        """
        Obter candles historicos REAIS da Binance

        Args:
            symbol: Par de trading (ex: BTCUSDT)
            timeframe: Timeframe em minutos
            count: Numero de candles

        Returns:
            DataFrame com OHLCV REAL ou None
        """
        if not self.session:
            await self.connect()

        # Mapear timeframe
        interval = self.timeframe_map.get(timeframe, "1m")

        try:
            # Endpoint de klines (candles)
            url = f"{self.base_url}/klines"
            params = {
                "symbol": symbol,
                "interval": interval,
                "limit": count
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    # Converter para DataFrame
                    df = pd.DataFrame(data, columns=[
                        'timestamp', 'open', 'high', 'low', 'close', 'volume',
                        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                        'taker_buy_quote', 'ignore'
                    ])

                    # Converter tipos
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    df['open'] = df['open'].astype(float)
                    df['high'] = df['high'].astype(float)
                    df['low'] = df['low'].astype(float)
                    df['close'] = df['close'].astype(float)
                    df['volume'] = df['volume'].astype(float)

                    # Selecionar colunas necessarias
                    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]

                    print(f"[BINANCE] OK {symbol} - {len(df)} candles REAIS obtidos")
                    return df
                else:
                    print(f"[BINANCE] ERRO HTTP {response.status} para {symbol}")
                    return None

        except Exception as e:
            print(f"[BINANCE] ERRO ao buscar {symbol}: {e}")
            return None

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Obter preco atual REAL

        Args:
            symbol: Par de trading

        Returns:
            Preco atual ou None
        """
        if not self.session:
            await self.connect()

        try:
            url = f"{self.base_url}/ticker/price"
            params = {"symbol": symbol}

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return float(data['price'])

        except Exception as e:
            print(f"[BINANCE] ERRO ao buscar preco {symbol}: {e}")

        return None

    async def is_market_open(self, symbol: str) -> bool:
        """
        Verificar se mercado esta aberto

        Cripto opera 24/7, sempre retorna True
        """
        return True

    def get_market_status(self) -> Dict:
        """
        Obter status do mercado

        Returns:
            Status do mercado Binance
        """
        return {
            "market": "Binance Crypto",
            "status": "open",
            "is_24_7": True,
            "available_pairs": len(self.trading_pairs),
            "description": "Mercado de criptomoedas 24/7"
        }
