"""
Real Market Data Client
Integrates with Binance API for real-time market data (FREE, no API key needed)
"""
import asyncio
import aiohttp
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import json


class RealMarketDataClient:
    """Client for Real Market Data using Binance API"""

    def __init__(self):
        """Initialize Real Market Data client"""
        self.base_url = "https://api.binance.com"
        self.session: Optional[aiohttp.ClientSession] = None

        # Map trading symbols to Binance format
        self.symbol_map = {
            # Crypto pairs (disponíveis na Binance)
            "BTCUSDT": {"binance": "BTCUSDT", "name": "Bitcoin/USDT"},
            "ETHUSDT": {"binance": "ETHUSDT", "name": "Ethereum/USDT"},
            "BNBUSDT": {"binance": "BNBUSDT", "name": "BNB/USDT"},
            "ADAUSDT": {"binance": "ADAUSDT", "name": "Cardano/USDT"},
            "XRPUSDT": {"binance": "XRPUSDT", "name": "Ripple/USDT"},
            "SOLUSDT": {"binance": "SOLUSDT", "name": "Solana/USDT"},
            "DOGEUSDT": {"binance": "DOGEUSDT", "name": "Dogecoin/USDT"},
            "MATICUSDT": {"binance": "MATICUSDT", "name": "Polygon/USDT"},
            "DOTUSDT": {"binance": "DOTUSDT", "name": "Polkadot/USDT"},
            "AVAXUSDT": {"binance": "AVAXUSDT", "name": "Avalanche/USDT"},
            "SHIBUSDT": {"binance": "SHIBUSDT", "name": "Shiba Inu/USDT"},
            "LINKUSDT": {"binance": "LINKUSDT", "name": "Chainlink/USDT"},
            "TRXUSDT": {"binance": "TRXUSDT", "name": "Tron/USDT"},
            "UNIUSDT": {"binance": "UNIUSDT", "name": "Uniswap/USDT"},
            "LTCUSDT": {"binance": "LTCUSDT", "name": "Litecoin/USDT"},
        }

        # Timeframe mapping (minutos -> Binance interval)
        self.timeframe_map = {
            1: "1m",
            3: "3m",
            5: "5m",
            15: "15m",
            30: "30m",
            60: "1h"
        }

    async def connect(self):
        """Establish connection"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        print("[RealMarketData] Conectado à API Binance (dados reais)")
        return True

    async def disconnect(self):
        """Disconnect"""
        if self.session:
            await self.session.close()
            self.session = None

    async def get_available_pairs(self, include_otc: bool = True) -> List[Dict]:
        """
        Get list of available trading pairs

        Returns:
            List of real trading pairs from Binance
        """
        pairs = []

        for symbol, data in self.symbol_map.items():
            pairs.append({
                "symbol": symbol,
                "name": data["name"],
                "is_otc": False,  # Binance não tem OTC
                "is_active": True
            })

        print(f"[RealMarketData] {len(pairs)} pares reais disponíveis")
        return pairs

    async def get_candles(
        self,
        symbol: str,
        timeframe: int = 5,
        limit: int = 100
    ) -> pd.DataFrame:
        """
        Get REAL candlestick data from Binance

        Args:
            symbol: Trading pair symbol (ex: BTCUSDT)
            timeframe: Timeframe in minutes
            limit: Number of candles to fetch

        Returns:
            DataFrame with REAL OHLCV data
        """
        if not self.session:
            await self.connect()

        # Converter símbolo
        if symbol not in self.symbol_map:
            print(f"[RealMarketData] AVISO Símbolo {symbol} não encontrado, usando BTCUSDT")
            symbol = "BTCUSDT"

        binance_symbol = self.symbol_map[symbol]["binance"]
        interval = self.timeframe_map.get(timeframe, "5m")

        try:
            # Fazer requisição REAL para Binance
            url = f"{self.base_url}/api/v3/klines"
            params = {
                "symbol": binance_symbol,
                "interval": interval,
                "limit": limit
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    # Converter para DataFrame
                    candles = []
                    for candle in data:
                        candles.append({
                            'timestamp': datetime.fromtimestamp(candle[0] / 1000),
                            'open': float(candle[1]),
                            'high': float(candle[2]),
                            'low': float(candle[3]),
                            'close': float(candle[4]),
                            'volume': float(candle[5])
                        })

                    df = pd.DataFrame(candles)
                    print(f"[RealMarketData] OK {len(df)} candles REAIS obtidos para {symbol}")
                    return df
                else:
                    print(f"[RealMarketData] ERRO Erro ao buscar dados: {response.status}")
                    return pd.DataFrame()

        except Exception as e:
            print(f"[RealMarketData] ERRO Erro: {e}")
            return pd.DataFrame()

    async def get_realtime_price(self, symbol: str) -> float:
        """
        Get REAL current price from Binance

        Args:
            symbol: Trading pair symbol

        Returns:
            Current real price
        """
        if not self.session:
            await self.connect()

        if symbol not in self.symbol_map:
            symbol = "BTCUSDT"

        binance_symbol = self.symbol_map[symbol]["binance"]

        try:
            url = f"{self.base_url}/api/v3/ticker/price"
            params = {"symbol": binance_symbol}

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    price = float(data['price'])
                    return price
                else:
                    return 0.0

        except Exception as e:
            print(f"[RealMarketData] Erro ao buscar preço: {e}")
            return 0.0


# Singleton instance
_client_instance: Optional[RealMarketDataClient] = None


def get_market_data_client() -> RealMarketDataClient:
    """Get or create Real Market Data client instance"""
    global _client_instance

    if _client_instance is None:
        _client_instance = RealMarketDataClient()

    return _client_instance
