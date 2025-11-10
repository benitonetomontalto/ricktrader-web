"""
Technical Indicators Calculator
"""
import pandas as pd
import numpy as np
from typing import Tuple


class TechnicalIndicators:
    """Calculate various technical indicators"""

    @staticmethod
    def calculate_ema(df: pd.DataFrame, period: int, column: str = 'close') -> pd.Series:
        """Calculate Exponential Moving Average"""
        return df[column].ewm(span=period, adjust=False).mean()

    @staticmethod
    def calculate_sma(df: pd.DataFrame, period: int, column: str = 'close') -> pd.Series:
        """Calculate Simple Moving Average"""
        return df[column].rolling(window=period).mean()

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range (Volatility)"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(period).mean()

        return atr

    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14, column: str = 'close') -> pd.Series:
        """Calculate Relative Strength Index"""
        delta = df[column].diff()

        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def calculate_bollinger_bands(
        df: pd.DataFrame,
        period: int = 20,
        std_dev: float = 2.0,
        column: str = 'close'
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands"""
        middle_band = df[column].rolling(window=period).mean()
        std = df[column].rolling(window=period).std()

        upper_band = middle_band + (std * std_dev)
        lower_band = middle_band - (std * std_dev)

        return upper_band, middle_band, lower_band

    @staticmethod
    def calculate_macd(
        df: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
        column: str = 'close'
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD"""
        ema_fast = df[column].ewm(span=fast, adjust=False).mean()
        ema_slow = df[column].ewm(span=slow, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    @staticmethod
    def detect_trend(df: pd.DataFrame, ema_short: int = 20, ema_long: int = 50) -> str:
        """Detect market trend (bullish, bearish, neutral)"""
        ema_s = TechnicalIndicators.calculate_ema(df, ema_short)
        ema_l = TechnicalIndicators.calculate_ema(df, ema_long)

        if len(ema_s) < 2 or len(ema_l) < 2:
            return "neutral"

        # Last values
        ema_s_last = ema_s.iloc[-1]
        ema_l_last = ema_l.iloc[-1]

        # Check trend
        if ema_s_last > ema_l_last:
            # Check if EMAs are rising
            if ema_s.iloc[-1] > ema_s.iloc[-3] and ema_l.iloc[-1] > ema_l.iloc[-3]:
                return "bullish"
            return "neutral"
        elif ema_s_last < ema_l_last:
            # Check if EMAs are falling
            if ema_s.iloc[-1] < ema_s.iloc[-3] and ema_l.iloc[-1] < ema_l.iloc[-3]:
                return "bearish"
            return "neutral"
        else:
            return "neutral"

    @staticmethod
    def is_high_volatility(df: pd.DataFrame, atr_period: int = 14, threshold: float = 1.5) -> bool:
        """Check if volatility is high"""
        atr = TechnicalIndicators.calculate_atr(df, atr_period)

        if len(atr) < atr_period * 2:
            return False

        current_atr = atr.iloc[-1]
        avg_atr = atr.iloc[-atr_period:].mean()

        return current_atr > (avg_atr * threshold)

    @staticmethod
    def is_volume_increasing(df: pd.DataFrame, period: int = 5) -> bool:
        """Check if volume is increasing"""
        if 'volume' not in df.columns or len(df) < period + 1:
            return False

        recent_volume = df['volume'].iloc[-period:].mean()
        previous_volume = df['volume'].iloc[-period * 2:-period].mean()

        return recent_volume > previous_volume * 1.2
