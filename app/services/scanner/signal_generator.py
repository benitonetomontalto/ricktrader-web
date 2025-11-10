"""
Trading Signal Generator
Combines Price Action, Indicators, and S/R levels to generate trading signals
"""
import pandas as pd
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from ...models.schemas import (
    TradingSignal,
    PriceActionPattern,
    SupportResistanceLevel,
    ScanConfig
)
from ..price_action.pattern_detector import PriceActionDetector
from ..price_action.support_resistance import SupportResistanceDetector
from ..indicators.technical_indicators import TechnicalIndicators


class SignalGenerator:
    """Generate trading signals based on multiple confluences"""

    def __init__(self, config: ScanConfig):
        """
        Initialize signal generator

        Args:
            config: Scan configuration
        """
        self.config = config
        self.pattern_detector = PriceActionDetector(sensitivity=config.sensitivity)
        self.sr_detector = SupportResistanceDetector()
        self.indicators = TechnicalIndicators()

        # LOG das configurações aplicadas
        print(f"[SignalGenerator] Configuração aplicada:")
        print(f"  - Sensibilidade: {config.sensitivity}")
        print(f"  - Timeframe: {config.timeframe}M")
        print(f"  - Somente OTC: {config.only_otc}")
        print(f"  - Somente Mercado Aberto: {config.only_open_market}")

    def generate_signal(
        self,
        symbol: str,
        df: pd.DataFrame
    ) -> Optional[TradingSignal]:
        """
        Generate trading signal for a symbol

        Args:
            symbol: Trading pair symbol
            df: DataFrame with OHLC data

        Returns:
            TradingSignal if valid signal found, None otherwise
        """
        min_candles = 5 if self.config.sensitivity == "aggressive" else 50
        if len(df) < min_candles:
            if self.config.sensitivity != "aggressive":
                return None
            # Criar padding mínimo duplicando última vela conhecida
            if len(df) == 0:
                return None
            last_row = df.iloc[-1]
            while len(df) < min_candles:
                new_row = last_row.copy()
                new_row.name = last_row.name + pd.Timedelta(minutes=1)
                df = pd.concat([df, new_row.to_frame().T])

        # Detect patterns
        patterns = self.pattern_detector.detect_patterns(df)
        if not patterns and self.config.sensitivity == "aggressive":
            last_close = df['close'].iloc[-1]
            last_open = df['open'].iloc[-1]
            pattern_type = 'bos_bullish' if last_close >= last_open else 'bos_bearish'
            pattern = PriceActionPattern(
                pattern_type=pattern_type,
                description='Momentum imediato detectado',
                candle_index=len(df) - 1
            )
            patterns = [pattern]
        elif not patterns:
            return None

        # Get the most recent pattern
        pattern = patterns[-1]

        # Detect support/resistance levels
        sr_levels = self.sr_detector.detect_levels(df)

        # Get current price
        current_price = df['close'].iloc[-1]

        # Check if near S/R level
        is_near, sr_level = self.sr_detector.is_near_level(current_price, sr_levels)

        # Determine signal direction
        direction = self._determine_direction(pattern, sr_level, df)
        if not direction and self.config.sensitivity == "aggressive":
            direction = "CALL" if df['close'].iloc[-1] >= df['close'].iloc[-2] else "PUT"
        if not direction:
            return None

        # Apply filters
        filters_ok = self._apply_filters(df, direction)
        if not filters_ok:
            if self.config.sensitivity != "aggressive":
                return None
            filters_ok = True  # Força aceitação no modo agressivo

        # Calculate confluences
        confluences = self._calculate_confluences(pattern, sr_level, df, direction)
        if not confluences:
            confluences.append('Momentum imediato favoravel')
        if self.config.sensitivity == "aggressive":
            confluences.append('Modo agressivo habilitado')

        # Calculate confidence
        confidence = self._calculate_confidence(confluences, pattern, sr_level)

        # Calculate entry and expiry times (FUTURO!)
        now = datetime.now()

        next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        entry_buffer = 1 if self.config.sensitivity == "aggressive" else 0
        entry_time = next_minute + timedelta(minutes=entry_buffer)

        expiry_minutes = max(self.config.timeframe, 2)
        expiry_time = entry_time + timedelta(minutes=expiry_minutes)

        # Generate signal
        signal = TradingSignal(
            signal_id=str(uuid.uuid4()),
            timestamp=now,  # Quando foi gerado
            symbol=symbol,
            timeframe=self.config.timeframe,
            direction=direction,
            entry_price=current_price,
            entry_time=entry_time,  # Quando entrar (futuro)
            expiry_time=expiry_time,  # Quando expira
            pattern=pattern.model_dump() if pattern else None,
            support_resistance=sr_level.model_dump() if (sr_level and is_near) else None,
            confluences=confluences,
            confidence=confidence,
            expiry_minutes=expiry_minutes
        )

        return signal

    def _determine_direction(
        self,
        pattern: PriceActionPattern,
        sr_level: Optional[SupportResistanceLevel],
        df: pd.DataFrame
    ) -> Optional[str]:
        """Determine signal direction (CALL or PUT) - VERSAO FLEXIVEL PARA GERAR MAIS SINAIS"""

        # Padroes claramente bullish - SEMPRE CALL
        if pattern.pattern_type in ["pin_bar", "engulfing_bullish", "bos_bullish"]:
            return "CALL"

        # Padroes claramente bearish - SEMPRE PUT
        if pattern.pattern_type in ["engulfing_bearish", "bos_bearish"]:
            return "PUT"

        # Doji - usar RSI para decidir direcao
        if pattern.pattern_type == "doji":
            rsi = self.indicators.calculate_rsi(df)
            if len(rsi) > 0:
                rsi_value = rsi.iloc[-1]
                return "CALL" if rsi_value < 50 else "PUT"
            return "CALL"  # Default CALL

        # Inside bar - usar tendencia
        if pattern.pattern_type == "inside_bar":
            trend = self.indicators.detect_trend(df)
            if trend == "bearish":
                return "PUT"
            else:
                return "CALL"  # Default ou bullish = CALL

        # Fallback - sempre gerar sinal (CALL por padrao)
        return "CALL"

    def _apply_filters(self, df: pd.DataFrame, direction: str) -> bool:
        """Apply various filters based on configuration - RELAXADO PARA MODO AGRESSIVO"""

        # Se sensitivity for aggressive, NAO APLICAR filtros rigorosos
        if self.config.sensitivity == "aggressive":
            return True  # Aceitar tudo no modo agressivo

        # Modo moderate/conservative: aplicar filtros
        # Volume filter
        if self.config.use_volume_filter:
            if not self.indicators.is_volume_increasing(df):
                return False

        # Volatility filter
        if self.config.use_volatility_filter:
            if self.indicators.is_high_volatility(df, threshold=2.0):
                return False

        # Trend filter
        if self.config.use_trend_filter:
            trend = self.indicators.detect_trend(df)
            if direction == "CALL" and trend == "bearish":
                return False
            if direction == "PUT" and trend == "bullish":
                return False

        return True

    def _calculate_confluences(
        self,
        pattern: PriceActionPattern,
        sr_level: Optional[SupportResistanceLevel],
        df: pd.DataFrame,
        direction: str
    ) -> List[str]:
        """Calculate all confluences supporting the signal"""
        confluences = []

        # Pattern confluence
        confluences.append(f"Padro: {pattern.description}")

        # Support/Resistance confluence
        if sr_level:
            confluences.append(
                f"{sr_level.type.capitalize()} em {sr_level.level:.5f} "
                f"(Fora: {sr_level.strength}/5)"
            )

        # Trend confluence
        trend = self.indicators.detect_trend(df)
        if (direction == "CALL" and trend == "bullish") or \
           (direction == "PUT" and trend == "bearish"):
            confluences.append(f"Tendncia {trend} favorvel")

        # Volume confluence
        if self.indicators.is_volume_increasing(df):
            confluences.append("Volume crescente confirmando movimento")

        # RSI confluence
        rsi = self.indicators.calculate_rsi(df)
        if len(rsi) > 0:
            rsi_value = rsi.iloc[-1]
            if direction == "CALL" and rsi_value < 40:
                confluences.append(f"RSI em sobrevenda ({rsi_value:.1f})")
            elif direction == "PUT" and rsi_value > 60:
                confluences.append(f"RSI em sobrecompra ({rsi_value:.1f})")

        # MACD confluence
        macd_line, signal_line, _ = self.indicators.calculate_macd(df)
        if len(macd_line) > 1 and len(signal_line) > 1:
            if direction == "CALL" and macd_line.iloc[-1] > signal_line.iloc[-1]:
                confluences.append("MACD bullish")
            elif direction == "PUT" and macd_line.iloc[-1] < signal_line.iloc[-1]:
                confluences.append("MACD bearish")

        return confluences

    def _calculate_confidence(
        self,
        confluences: List[str],
        pattern: PriceActionPattern,
        sr_level: Optional[SupportResistanceLevel]
    ) -> float:
        """Calculate signal confidence (0-100)"""
        confidence = 50.0  # Base confidence

        # Add points for each confluence
        confidence += len(confluences) * 5

        # Strong patterns add more confidence
        if pattern.pattern_type in ["engulfing_bullish", "engulfing_bearish"]:
            confidence += 15
        elif pattern.pattern_type in ["bos_bullish", "bos_bearish"]:
            confidence += 10

        # Strong S/R level adds confidence
        if sr_level:
            confidence += sr_level.strength * 3

        # Cap at 95 e garante base maior para modo agressivo
        if self.config.sensitivity == 'aggressive':
            confidence = max(confidence, 55.0)
        return min(confidence, 95.0)
