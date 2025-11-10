"""
FOREX + OTC Data Client - SEM LIMITE
Usa dados gratuitos de APIs públicas para FOREX e simula OTC
"""
import asyncio
import aiohttp
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import random


class ForexOTCDataClient:
    """Cliente FOREX + OTC usando APIs gratuitas SEM LIMITE"""

    def __init__(self):
        """Initialize FOREX + OTC client"""
        self.session: Optional[aiohttp.ClientSession] = None

        # Pares FOREX principais (dados reais via exchangerate-api.com - GRATIS e SEM LIMITE)
        self.forex_pairs = {
            "EURUSD": {"name": "Euro/Dólar", "is_otc": False},
            "GBPUSD": {"name": "Libra/Dólar", "is_otc": False},
            "USDJPY": {"name": "Dólar/Iene", "is_otc": False},
            "AUDUSD": {"name": "Dólar Australiano/Dólar", "is_otc": False},
            "USDCAD": {"name": "Dólar/Dólar Canadense", "is_otc": False},
            "NZDUSD": {"name": "Dólar Neozelandês/Dólar", "is_otc": False},
            "EURGBP": {"name": "Euro/Libra", "is_otc": False},
            "EURJPY": {"name": "Euro/Iene", "is_otc": False},
            "GBPJPY": {"name": "Libra/Iene", "is_otc": False},
            "AUDJPY": {"name": "Dólar Australiano/Iene", "is_otc": False},
            "USDCHF": {"name": "Dólar/Franco Suíço", "is_otc": False},
            "EURCHF": {"name": "Euro/Franco Suíço", "is_otc": False},
        }

        # Pares OTC (IQ Option) - Mesmos pares mas com horários OTC
        self.otc_pairs = {
            "EURUSD-OTC": {"name": "Euro/Dólar (OTC)", "is_otc": True, "base": "EURUSD"},
            "GBPUSD-OTC": {"name": "Libra/Dólar (OTC)", "is_otc": True, "base": "GBPUSD"},
            "USDJPY-OTC": {"name": "Dólar/Iene (OTC)", "is_otc": True, "base": "USDJPY"},
            "AUDUSD-OTC": {"name": "Dólar Australiano/Dólar (OTC)", "is_otc": True, "base": "AUDUSD"},
            "EURJPY-OTC": {"name": "Euro/Iene (OTC)", "is_otc": True, "base": "EURJPY"},
            "GBPJPY-OTC": {"name": "Libra/Iene (OTC)", "is_otc": True, "base": "GBPJPY"},
            "USDCHF-OTC": {"name": "Dólar/Franco Suíço (OTC)", "is_otc": True, "base": "USDCHF"},
            "EURGBP-OTC": {"name": "Euro/Libra (OTC)", "is_otc": True, "base": "EURGBP"},
        }

        # Cache de taxas (para reduzir chamadas de API)
        self.rates_cache = {}
        self.cache_time = None

    async def connect(self):
        """Estabelecer conexao"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        print("[FOREX+OTC] OK Conectado (dados REAIS de FOREX)")
        print(f"[FOREX+OTC] {len(self.forex_pairs)} pares FOREX + {len(self.otc_pairs)} pares OTC")
        print("[FOREX+OTC] SEM LIMITE de requisicoes!")
        return True

    async def disconnect(self):
        """Desconectar"""
        if self.session:
            await self.session.close()
            self.session = None

    async def get_available_pairs(self, include_otc: bool = True) -> List[Dict]:
        """
        Obter lista de pares disponiveis

        Args:
            include_otc: Incluir pares OTC

        Returns:
            Lista de pares FOREX + OTC
        """
        pairs = []

        # Adicionar pares FOREX
        for symbol, data in self.forex_pairs.items():
            pairs.append({
                "symbol": symbol,
                "name": data["name"],
                "is_otc": False,
                "is_active": True
            })

        # Adicionar pares OTC se solicitado
        if include_otc:
            for symbol, data in self.otc_pairs.items():
                pairs.append({
                    "symbol": symbol,
                    "name": data["name"],
                    "is_otc": True,
                    "is_active": True
                })

        return pairs

    async def _get_current_rates(self) -> Dict:
        """Obter taxas atuais de cambio (com cache de 1 minuto)"""
        now = datetime.now()

        # Usar cache se recente (< 1 min)
        if self.cache_time and (now - self.cache_time).seconds < 60:
            return self.rates_cache

        try:
            # API GRATUITA e SEM LIMITE: exchangerate-api.com
            url = "https://api.exchangerate-api.com/v4/latest/USD"

            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    self.rates_cache = data['rates']
                    self.cache_time = now
                    print(f"[FOREX+OTC] Taxas atualizadas: {len(self.rates_cache)} moedas")
                    return self.rates_cache
        except Exception as e:
            print(f"[FOREX+OTC] Erro ao obter taxas: {e}")

        # Se falhar, retornar cache antigo ou taxas default
        if self.rates_cache:
            return self.rates_cache

        # Taxas default como fallback
        return {
            "EUR": 0.92, "GBP": 0.79, "JPY": 149.50, "AUD": 1.52,
            "CAD": 1.36, "NZD": 1.65, "CHF": 0.88
        }

    def _calculate_pair_rate(self, symbol: str, rates: Dict) -> float:
        """Calcular taxa de um par FOREX"""
        # Remover -OTC se presente
        base_symbol = symbol.replace("-OTC", "")

        # Pares diretos USD (ex: EURUSD, GBPUSD)
        if base_symbol.endswith("USD"):
            currency = base_symbol[:3]
            if currency in rates:
                return 1.0 / rates[currency]  # Inverter

        # Pares com USD no inicio (ex: USDJPY, USDCHF)
        elif base_symbol.startswith("USD"):
            currency = base_symbol[3:]
            if currency in rates:
                return rates[currency]

        # Pares cruzados (ex: EURGBP, EURJPY)
        else:
            base = base_symbol[:3]
            quote = base_symbol[3:]
            if base in rates and quote in rates:
                # Calcular taxa cruzada via USD
                return rates[quote] / rates[base]

        # Fallback
        return 1.0

    async def get_candles(
        self,
        symbol: str,
        timeframe: int = 1,
        limit: int = 100
    ) -> Optional[pd.DataFrame]:
        """
        Gerar candles FOREX/OTC baseados em taxas reais + variacao simulada

        Args:
            symbol: Par FOREX ou OTC
            timeframe: Timeframe em minutos
            limit: Numero de candles

        Returns:
            DataFrame com OHLCV
        """
        if not self.session:
            await self.connect()

        # Obter taxa atual real
        rates = await self._get_current_rates()
        current_rate = self._calculate_pair_rate(symbol, rates)

        # Gerar candles historicos com variacao realista
        candles = []
        now = datetime.now()

        for i in range(limit):
            # Timestamp do candle (mais antigo primeiro)
            timestamp = now - timedelta(minutes=(limit - i) * timeframe)

            # Variacao pequena para simular movimento real (0.1% - 0.3%)
            variation = random.uniform(-0.003, 0.003)
            base_price = current_rate * (1 + variation * (limit - i) / limit)

            # OHLC com micro-variacao
            open_price = base_price
            high_price = base_price * (1 + random.uniform(0.0001, 0.0015))
            low_price = base_price * (1 - random.uniform(0.0001, 0.0015))
            close_price = base_price * (1 + random.uniform(-0.0008, 0.0008))

            # Volume simulado
            volume = random.uniform(1000, 5000)

            candles.append({
                'timestamp': timestamp,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume
            })

        df = pd.DataFrame(candles)
        print(f"[FOREX+OTC] OK {symbol} - {len(df)} candles gerados (taxa atual: {current_rate:.5f})")
        return df

    async def get_realtime_price(self, symbol: str) -> float:
        """Obter preco atual"""
        rates = await self._get_current_rates()
        return self._calculate_pair_rate(symbol, rates)

    async def is_market_open(self, symbol: str) -> bool:
        """Verificar se mercado esta aberto"""
        # OTC opera em horarios especiais (fora do horario FOREX normal)
        if "-OTC" in symbol:
            # OTC: disponivel quando FOREX fecha (fim de semana e fora de horario)
            now = datetime.now()
            hour = now.hour
            weekday = now.weekday()

            # Sabado/Domingo: OTC aberto
            if weekday >= 5:
                return True

            # Dias uteis: OTC aberto fora do horario FOREX (antes 8h ou depois 18h)
            if hour < 8 or hour >= 18:
                return True

            return False
        else:
            # FOREX: Segunda a Sexta, 8h-18h (simplificado)
            now = datetime.now()
            hour = now.hour
            weekday = now.weekday()

            if weekday < 5 and 8 <= hour < 18:
                return True

            return False


# Singleton instance
_client_instance: Optional[ForexOTCDataClient] = None


def get_forex_otc_client() -> ForexOTCDataClient:
    """Get or create FOREX+OTC client instance"""
    global _client_instance

    if _client_instance is None:
        _client_instance = ForexOTCDataClient()

    return _client_instance
