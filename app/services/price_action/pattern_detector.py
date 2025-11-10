"""
Price Action Pattern Detector
Detects classic candlestick patterns for binary options trading
"""
import pandas as pd
import numpy as np
from typing import List, Optional, Tuple
from ...models.schemas import PriceActionPattern


class PriceActionDetector:
    """Detect Price Action patterns in candlestick data"""

    def __init__(self, sensitivity: str = "moderate"):
        """
        Initialize detector with sensitivity level

        Args:
            sensitivity: "conservative", "moderate", or "aggressive"
        """
        self.sensitivity = sensitivity
        self.thresholds = self._get_thresholds()

    def _get_thresholds(self) -> dict:
        """Get detection thresholds based on sensitivity"""
        thresholds = {
            "conservative": {
                "pin_bar_ratio": 3.0,
                "pin_bar_wick": 0.66,
                "engulfing_body": 1.2,
                "inside_bar_ratio": 0.8,
                "doji_body": 0.1,
            },
            "moderate": {
                "pin_bar_ratio": 2.5,
                "pin_bar_wick": 0.60,
                "engulfing_body": 1.1,
                "inside_bar_ratio": 0.85,
                "doji_body": 0.15,
            },
            "aggressive": {
                "pin_bar_ratio": 2.0,
                "pin_bar_wick": 0.55,
                "engulfing_body": 1.0,
                "inside_bar_ratio": 0.90,
                "doji_body": 0.20,
            }
        }
        return thresholds.get(self.sensitivity, thresholds["moderate"])

    def detect_patterns(self, df: pd.DataFrame) -> List[PriceActionPattern]:
        """
        Detect all patterns in the dataframe

        Args:
            df: DataFrame with OHLC data

        Returns:
            List of detected patterns
        """
        patterns = []

        if len(df) < 3:
            return patterns

        # Check last 3 candles for patterns
        for i in range(len(df) - 3, len(df)):
            if i < 1:
                continue

            # Pin Bar (Hammer/Shooting Star)
            pin = self._detect_pin_bar(df, i)
            if pin:
                patterns.append(pin)

            # Engulfing patterns
            engulf = self._detect_engulfing(df, i)
            if engulf:
                patterns.append(engulf)

            # Inside Bar
            inside = self._detect_inside_bar(df, i)
            if inside:
                patterns.append(inside)

            # Doji
            doji = self._detect_doji(df, i)
            if doji:
                patterns.append(doji)

        # Break of Structure (needs more candles)
        if len(df) >= 5:
            bos = self._detect_break_of_structure(df)
            if bos:
                patterns.append(bos)

        return patterns

    def _detect_pin_bar(self, df: pd.DataFrame, index: int) -> Optional[PriceActionPattern]:
        """Detect Pin Bar (Hammer or Shooting Star)"""
        candle = df.iloc[index]

        o, h, l, c = candle['open'], candle['high'], candle['low'], candle['close']
        body = abs(c - o)
        total_range = h - l

        if total_range == 0:
            return None

        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l

        # Bullish Pin Bar (Hammer)
        if lower_wick > body * self.thresholds["pin_bar_ratio"]:
            if lower_wick / total_range >= self.thresholds["pin_bar_wick"]:
                return PriceActionPattern(
                    pattern_type="pin_bar",
                    description="Pin Bar de Alta (Martelo) - Rejeição de preços baixos",
                    candle_index=index
                )

        # Bearish Pin Bar (Shooting Star)
        if upper_wick > body * self.thresholds["pin_bar_ratio"]:
            if upper_wick / total_range >= self.thresholds["pin_bar_wick"]:
                return PriceActionPattern(
                    pattern_type="pin_bar",
                    description="Pin Bar de Baixa (Estrela Cadente) - Rejeição de preços altos",
                    candle_index=index
                )

        return None

    def _detect_engulfing(self, df: pd.DataFrame, index: int) -> Optional[PriceActionPattern]:
        """Detect Engulfing patterns"""
        if index < 1:
            return None

        current = df.iloc[index]
        previous = df.iloc[index - 1]

        curr_body = abs(current['close'] - current['open'])
        prev_body = abs(previous['close'] - previous['open'])

        if prev_body == 0:
            return None

        # Bullish Engulfing
        if (current['close'] > current['open'] and  # Current is bullish
            previous['close'] < previous['open'] and  # Previous is bearish
            current['open'] <= previous['close'] and  # Opens at or below previous close
            current['close'] > previous['open'] and  # Closes above previous open
            curr_body > prev_body * self.thresholds["engulfing_body"]):

            return PriceActionPattern(
                pattern_type="engulfing_bullish",
                description="Engolfo de Alta - Reversão bullish forte",
                candle_index=index
            )

        # Bearish Engulfing
        if (current['close'] < current['open'] and  # Current is bearish
            previous['close'] > previous['open'] and  # Previous is bullish
            current['open'] >= previous['close'] and  # Opens at or above previous close
            current['close'] < previous['open'] and  # Closes below previous open
            curr_body > prev_body * self.thresholds["engulfing_body"]):

            return PriceActionPattern(
                pattern_type="engulfing_bearish",
                description="Engolfo de Baixa - Reversão bearish forte",
                candle_index=index
            )

        return None

    def _detect_inside_bar(self, df: pd.DataFrame, index: int) -> Optional[PriceActionPattern]:
        """Detect Inside Bar pattern"""
        if index < 1:
            return None

        current = df.iloc[index]
        previous = df.iloc[index - 1]

        # Current candle is completely inside previous candle
        if (current['high'] <= previous['high'] and
            current['low'] >= previous['low']):

            curr_range = current['high'] - current['low']
            prev_range = previous['high'] - previous['low']

            if prev_range > 0 and curr_range / prev_range <= self.thresholds["inside_bar_ratio"]:
                return PriceActionPattern(
                    pattern_type="inside_bar",
                    description="Inside Bar - Consolidação antes de movimento",
                    candle_index=index
                )

        return None

    def _detect_doji(self, df: pd.DataFrame, index: int) -> Optional[PriceActionPattern]:
        """Detect Doji pattern"""
        candle = df.iloc[index]

        o, h, l, c = candle['open'], candle['high'], candle['low'], candle['close']
        body = abs(c - o)
        total_range = h - l

        if total_range == 0:
            return None

        # Body is very small compared to total range
        if body / total_range <= self.thresholds["doji_body"]:
            return PriceActionPattern(
                pattern_type="doji",
                description="Doji - Indecisão do mercado, possível reversão",
                candle_index=index
            )

        return None

    def _detect_break_of_structure(self, df: pd.DataFrame) -> Optional[PriceActionPattern]:
        """Detect Break of Structure (BOS)"""
        if len(df) < 5:
            return None

        # Get recent highs and lows
        recent_data = df.iloc[-5:]
        highs = recent_data['high'].values
        lows = recent_data['low'].values

        # Bullish BOS: Break above recent high
        if len(highs) >= 3:
            prev_high = max(highs[:-1])
            current_high = highs[-1]

            if current_high > prev_high * 1.001:  # 0.1% buffer
                return PriceActionPattern(
                    pattern_type="bos_bullish",
                    description="Break of Structure de Alta - Rompimento de topo",
                    candle_index=len(df) - 1
                )

        # Bearish BOS: Break below recent low
        if len(lows) >= 3:
            prev_low = min(lows[:-1])
            current_low = lows[-1]

            if current_low < prev_low * 0.999:  # 0.1% buffer
                return PriceActionPattern(
                    pattern_type="bos_bearish",
                    description="Break of Structure de Baixa - Rompimento de fundo",
                    candle_index=len(df) - 1
                )

        return None
