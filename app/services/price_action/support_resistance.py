"""
Support and Resistance Level Detection
"""
import pandas as pd
import numpy as np
from typing import List
from ...models.schemas import SupportResistanceLevel


class SupportResistanceDetector:
    """Detect support and resistance levels"""

    def __init__(self, lookback: int = 20, tolerance: float = 0.0005):
        """
        Initialize detector

        Args:
            lookback: Number of candles to look back
            tolerance: Price tolerance for level clustering (0.05%)
        """
        self.lookback = lookback
        self.tolerance = tolerance

    def detect_levels(
        self,
        df: pd.DataFrame,
        max_levels: int = 5
    ) -> List[SupportResistanceLevel]:
        """
        Detect support and resistance levels

        Args:
            df: DataFrame with OHLC data
            max_levels: Maximum number of levels to return

        Returns:
            List of support/resistance levels
        """
        if len(df) < self.lookback:
            return []

        # Get recent data
        recent_df = df.iloc[-self.lookback:]

        # Find pivot points (local highs and lows)
        pivots = self._find_pivot_points(recent_df)

        # Cluster nearby levels
        levels = self._cluster_levels(pivots)

        # Calculate level strength
        levels_with_strength = []
        current_price = df['close'].iloc[-1]

        for level_price, level_type in levels:
            touches = self._count_touches(df, level_price)
            strength = min(touches, 5)  # Max strength is 5

            levels_with_strength.append(
                SupportResistanceLevel(
                    level=level_price,
                    type=level_type,
                    strength=strength,
                    touches=touches
                )
            )

        # Sort by strength and proximity to current price
        levels_with_strength.sort(
            key=lambda x: (x.strength, -abs(x.level - current_price)),
            reverse=True
        )

        return levels_with_strength[:max_levels]

    def _find_pivot_points(self, df: pd.DataFrame) -> List[tuple]:
        """Find pivot highs and lows"""
        pivots = []

        for i in range(2, len(df) - 2):
            # Pivot High (resistance)
            if (df['high'].iloc[i] > df['high'].iloc[i-1] and
                df['high'].iloc[i] > df['high'].iloc[i-2] and
                df['high'].iloc[i] > df['high'].iloc[i+1] and
                df['high'].iloc[i] > df['high'].iloc[i+2]):
                pivots.append((df['high'].iloc[i], 'resistance'))

            # Pivot Low (support)
            if (df['low'].iloc[i] < df['low'].iloc[i-1] and
                df['low'].iloc[i] < df['low'].iloc[i-2] and
                df['low'].iloc[i] < df['low'].iloc[i+1] and
                df['low'].iloc[i] < df['low'].iloc[i+2]):
                pivots.append((df['low'].iloc[i], 'support'))

        return pivots

    def _cluster_levels(self, pivots: List[tuple]) -> List[tuple]:
        """Cluster nearby price levels"""
        if not pivots:
            return []

        clustered = []
        sorted_pivots = sorted(pivots, key=lambda x: x[0])

        current_cluster = [sorted_pivots[0]]

        for pivot in sorted_pivots[1:]:
            # If pivot is close to current cluster, add it
            cluster_avg = np.mean([p[0] for p in current_cluster])

            if abs(pivot[0] - cluster_avg) / cluster_avg <= self.tolerance:
                current_cluster.append(pivot)
            else:
                # Finish current cluster and start new one
                avg_price = np.mean([p[0] for p in current_cluster])
                # Determine if support or resistance (most common in cluster)
                types = [p[1] for p in current_cluster]
                level_type = max(set(types), key=types.count)

                clustered.append((avg_price, level_type))
                current_cluster = [pivot]

        # Add last cluster
        if current_cluster:
            avg_price = np.mean([p[0] for p in current_cluster])
            types = [p[1] for p in current_cluster]
            level_type = max(set(types), key=types.count)
            clustered.append((avg_price, level_type))

        return clustered

    def _count_touches(self, df: pd.DataFrame, level: float) -> int:
        """Count how many times price touched a level"""
        touches = 0
        tolerance_range = level * self.tolerance

        for i in range(len(df)):
            high = df['high'].iloc[i]
            low = df['low'].iloc[i]

            # Check if candle touched the level
            if low <= level + tolerance_range and high >= level - tolerance_range:
                touches += 1

        return touches

    def is_near_level(
        self,
        price: float,
        levels: List[SupportResistanceLevel],
        tolerance: float = 0.001
    ) -> tuple[bool, SupportResistanceLevel]:
        """
        Check if price is near any support/resistance level

        Returns:
            (is_near, level_object or None)
        """
        for level in levels:
            if abs(price - level.level) / price <= tolerance:
                return True, level

        return False, None
