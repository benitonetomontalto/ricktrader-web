"""IQ Option API Client"""
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class IQOptionClient:
    def __init__(self):
        self.api = None
        self.is_connected = False
        self.email = None
        self.last_activity = datetime.now()
        self.otc_pairs = {
            "EURUSD-OTC": {"name": "EUR/USD OTC", "type": "forex"},
            "GBPUSD-OTC": {"name": "GBP/USD OTC", "type": "forex"},
            "USDJPY-OTC": {"name": "USD/JPY OTC", "type": "forex"},
        }
    
    async def connect(self, email: str, password: str) -> bool:
        try:
            from iqoptionapi.stable_api import IQ_Option
            self.api = IQ_Option(email, password)
            check, reason = await asyncio.to_thread(self.api.connect)
            if check:
                self.is_connected = True
                self.email = email
                await asyncio.to_thread(self.api.change_balance, "PRACTICE")
                return True
            return False
        except Exception as e:
            logger.error(f"Error: {e}")
            return False
