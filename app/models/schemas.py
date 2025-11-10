"""
Pydantic schemas for request/response validation
"""
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


# Authentication
class LoginRequest(BaseModel):
    username: str
    password: Optional[str] = None  # Senha opcional
    access_token: Optional[str] = None
    iqoption_email: Optional[str] = None
    iqoption_password: Optional[str] = None
    iqoption_account_type: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    access_message: Optional[str] = None
    access_token_label: Optional[str] = None
    iq_option_connected: Optional[bool] = None
    iq_option_message: Optional[str] = None
    iq_option_balance: Optional[float] = None
    iq_option_account_type: Optional[str] = None
    iq_option_two_factor_required: Optional[bool] = None
    iq_option_two_factor_message: Optional[str] = None


# Trading Pair
class TradingPair(BaseModel):
    symbol: str
    name: str
    is_otc: bool = False
    is_active: bool = True
    market_type: Optional[str] = None


# Candle Data
class Candle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


# Price Action Pattern
class PriceActionPattern(BaseModel):
    pattern_type: Literal[
        "pin_bar",
        "engulfing_bullish",
        "engulfing_bearish",
        "inside_bar",
        "doji",
        "bos_bullish",
        "bos_bearish"
    ]
    description: str
    candle_index: int


# Support/Resistance Level
class SupportResistanceLevel(BaseModel):
    level: float
    type: Literal["support", "resistance"]
    strength: int = Field(ge=1, le=5)
    touches: int


# Trading Signal
class TradingSignal(BaseModel):
    signal_id: str
    timestamp: datetime  # Quando o sinal foi gerado
    symbol: str
    timeframe: int
    direction: Literal["CALL", "PUT"]
    entry_price: float
    entry_time: Optional[datetime] = None  # Horário de entrada (futuro - próxima vela)
    expiry_time: Optional[datetime] = None  # Horário de expiração
    pattern: PriceActionPattern
    support_resistance: Optional[SupportResistanceLevel] = None
    confluences: List[str] = []
    confidence: float = Field(ge=0, le=100)
    expiry_minutes: int = 5


# Scan Configuration
class ScanConfig(BaseModel):
    mode: Literal["manual", "auto"] = "auto"
    symbols: Optional[List[str]] = None
    timeframe: int = Field(default=5, ge=1, le=60)
    sensitivity: Literal["conservative", "moderate", "aggressive"] = "moderate"
    use_volume_filter: bool = True
    use_volatility_filter: bool = True
    use_trend_filter: bool = True
    only_otc: bool = False
    only_open_market: bool = False  # Filter for open market only (not OTC)


# Statistics
class TradingStats(BaseModel):
    total_signals: int
    win_signals: int
    loss_signals: int
    winrate: float
    best_pairs: List[dict]
    average_response_time: float


# Alert Configuration
class AlertConfig(BaseModel):
    sound_enabled: bool = True
    visual_enabled: bool = True
    telegram_enabled: bool = False
    pre_signal_alert: bool = False


# User Settings
class UserSettings(BaseModel):
    scan_config: ScanConfig
    alert_config: AlertConfig
    mboption_token: Optional[str] = None


# Signal Response (detailed)
class SignalResponse(BaseModel):
    signal: TradingSignal
    chart_data: List[Candle]
    indicators: dict
    explanation: str
