"""IQ Option API Client - Real implementation wrapper.

This module re-exports the real IQ Option client used by the scanner so that
other parts of the codebase can keep importing from app.services.iqoption.
"""
from ..scanner.iqoption_client import IQOptionClient

__all__ = ["IQOptionClient"]
