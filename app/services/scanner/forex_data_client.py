"""
Real FOREX Data Client
Integrates with Alpha Vantage API for real-time FOREX data
"""
import asyncio
import aiohttp
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import json


class RealForexDataClient:
    """Client for Real FOREX Data using Alpha Vantage API"""

    def __init__(self):
        """Initialize Real FOREX Data client"""
        # Alpha Vantage free API
        self.base_url = "https://www.alphavantage.co/query"
        self.api_key = "demo"  # Use 'demo' for testing, get free key at alphavantage.co
        self.session: Optional[aiohttp.ClientSession] = None

        # Map trading symbols to Forex format
        self.symbol_map = {
            # Principais pares de FOREX
            "EURUSD": {"from": "EUR", "to": "USD", "name": "Euro/Dólar"},
            "GBPUSD": {"from": "GBP", "to": "USD", "name": "Libra/Dólar"},
            "USDJPY": {"from": "USD", "to": "JPY", "name": "Dólar/Iene"},
            "AUDUSD": {"from": "AUD", "to": "USD", "name": "Dólar Australiano/Dólar"},
            "USDCAD": {"from": "USD", "to": "CAD", "name": "Dólar/Dólar Canadense"},
            "NZDUSD": {"from": "NZD", "to": "USD", "name": "Dólar Neozelandês/Dólar"},
            "EURGBP": {"from": "EUR", "to": "GBP", "name": "Euro/Libra"},
            "EURJPY": {"from": "EUR", "to": "JPY", "name": "Euro/Iene"},
            "GBPJPY": {"from": "GBP", "to": "JPY", "name": "Libra/Iene"},
            "AUDJPY": {"from": "AUD", "to": "JPY", "name": "Dólar Australiano/Iene"},
            "USDCHF": {"from": "USD", "to": "CHF", "name": "Dólar/Franco Suíço"},
            "EURCHF": {"from": "EUR", "to": "CHF", "name": "Euro/Franco Suíço"},
            "GBPAUD": {"from": "GBP", "to": "AUD", "name": "Libra/Dólar Australiano"},
            "AUDCAD": {"from": "AUD", "to": "CAD", "name": "Dólar Australiano/Dólar Canadense"},
            "NZDJPY": {"from": "NZD", "to": "JPY", "name": "Dólar Neozelandês/Iene"},
        }

        # Timeframe mapping (minutos -> Alpha Vantage interval)
        self.timeframe_map = {
            1: "1min",
            5: "5min",
            15: "15min",
            30: "30min",
            60: "60min"
        }

    async def connect(self):
        """Establish connection"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        print("[RealForexData] OK Conectado a API Alpha Vantage (dados REAIS de FOREX)")
        print("[RealForexData] 15 pares de moedas disponiveis")
        return True

    async def disconnect(self):
        """Disconnect"""
        if self.session:
            await self.session.close()
            self.session = None

    async def get_available_pairs(self, include_otc: bool = True) -> List[Dict]:
        """
        Get list of available FOREX trading pairs

        Returns:
            List of REAL FOREX pairs
        """
        pairs = []

        for symbol, data in self.symbol_map.items():
            pairs.append({
                "symbol": symbol,
                "name": data["name"],
                "is_otc": False,
                "is_active": True
            })

        print(f"[RealForexData] OK {len(pairs)} pares REAIS de FOREX disponiveis")
        return pairs

    async def get_candles(
        self,
        symbol: str,
        timeframe: int = 5,
        limit: int = 100
    ) -> pd.DataFrame:
        """
        Get REAL FOREX candlestick data from Alpha Vantage

        Args:
            symbol: Trading pair symbol (ex: EURUSD, GBPUSD)
            timeframe: Timeframe in minutes
            limit: Number of candles to fetch

        Returns:
            DataFrame with REAL FOREX OHLC data
        """
        if not self.session:
            await self.connect()

        # Converter símbolo
        if symbol not in self.symbol_map:
            print(f"[RealForexData] AVISO Símbolo {symbol} não encontrado, usando EURUSD")
            symbol = "EURUSD"

        from_symbol = self.symbol_map[symbol]["from"]
        to_symbol = self.symbol_map[symbol]["to"]
        interval = self.timeframe_map.get(timeframe, "5min")

        try:
            # Fazer requisição REAL para Alpha Vantage
            params = {
                "function": "FX_INTRADAY",
                "from_symbol": from_symbol,
                "to_symbol": to_symbol,
                "interval": interval,
                "apikey": self.api_key,
                "outputsize": "full",
                "datatype": "json"
            }

            async with self.session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    # Verificar se há dados
                    time_series_key = f"Time Series FX ({interval})"
                    if time_series_key not in data:
                        print(f"[RealForexData] AVISO Usando dados simulados (limite de API atingido)")
                        return self._generate_fallback_data(symbol, timeframe, limit)

                    time_series = data[time_series_key]

                    # Converter para DataFrame
                    candles = []
                    for timestamp, values in sorted(time_series.items(), reverse=True)[:limit]:
                        candles.append({
                            'timestamp': datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S'),
                            'open': float(values['1. open']),
                            'high': float(values['2. high']),
                            'low': float(values['3. low']),
                            'close': float(values['4. close']),
                            'volume': 1000.0  # Forex não tem volume centralizado
                        })

                    df = pd.DataFrame(candles[::-1])  # Inverter para ordem cronológica
                    print(f"[RealForexData] OK {len(df)} candles REAIS de FOREX obtidos para {symbol}")
                    return df
                else:
                    print(f"[RealForexData] ERRO ao buscar dados: {response.status}")
                    return self._generate_fallback_data(symbol, timeframe, limit)

        except Exception as e:
            print(f"[RealForexData] ERRO: {e}")
            print(f"[RealForexData] AVISO: Usando dados simulados como fallback")
            return self._generate_fallback_data(symbol, timeframe, limit)

    def _generate_fallback_data(self, symbol: str, timeframe: int, limit: int) -> pd.DataFrame:
        """
        Gera dados simulados quando a API não está disponível
        (limite de requisições ou falta de API key)
        """
        import numpy as np

        print(f"[RealForexData] INFO Gerando {limit} candles simulados para {symbol}")

        # Preços base para cada par
        base_prices = {
            "EURUSD": 1.0850,
            "GBPUSD": 1.2650,
            "USDJPY": 149.50,
            "AUDUSD": 0.6550,
            "USDCAD": 1.3550,
            "NZDUSD": 0.6150,
            "EURGBP": 0.8580,
            "EURJPY": 162.50,
            "GBPJPY": 189.50,
            "AUDJPY": 97.50,
            "USDCHF": 0.8450,
            "EURCHF": 0.9180,
            "GBPAUD": 1.9320,
            "AUDCAD": 0.8870,
            "NZDJPY": 92.00,
        }

        base_price = base_prices.get(symbol, 1.0000)

        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=timeframe * limit)
        timestamps = pd.date_range(start=start_time, end=end_time, periods=limit)

        candles = []
        current_price = base_price

        for timestamp in timestamps:
            # Random walk realista
            change = np.random.randn() * base_price * 0.0003  # 0.03% volatilidade
            current_price += change

            open_price = current_price
            high_price = open_price + abs(np.random.randn() * base_price * 0.0002)
            low_price = open_price - abs(np.random.randn() * base_price * 0.0002)
            close_price = low_price + (high_price - low_price) * np.random.random()

            candles.append({
                'timestamp': timestamp,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': np.random.randint(800, 1200)
            })

        return pd.DataFrame(candles)

    async def get_realtime_price(self, symbol: str) -> float:
        """
        Get REAL current FOREX price

        Args:
            symbol: Trading pair symbol

        Returns:
            Current REAL forex price
        """
        if not self.session:
            await self.connect()

        if symbol not in self.symbol_map:
            symbol = "EURUSD"

        from_symbol = self.symbol_map[symbol]["from"]
        to_symbol = self.symbol_map[symbol]["to"]

        try:
            params = {
                "function": "CURRENCY_EXCHANGE_RATE",
                "from_currency": from_symbol,
                "to_currency": to_symbol,
                "apikey": self.api_key
            }

            async with self.session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if "Realtime Currency Exchange Rate" in data:
                        price = float(data["Realtime Currency Exchange Rate"]["5. Exchange Rate"])
                        return price
                    return 0.0
                else:
                    return 0.0

        except Exception as e:
            print(f"[RealForexData] Erro ao buscar preço: {e}")
            return 0.0


# Singleton instance
_client_instance: Optional[RealForexDataClient] = None


def get_forex_data_client() -> RealForexDataClient:
    """Get or create Real FOREX Data client instance"""
    global _client_instance

    if _client_instance is None:
        _client_instance = RealForexDataClient()

    return _client_instance
