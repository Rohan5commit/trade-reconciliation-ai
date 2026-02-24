from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class TradeConnector(ABC):
    """Abstract base class for all trade source connectors."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.source_name = self.__class__.__name__

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to source system."""

    @abstractmethod
    def fetch_trades(self, from_date: datetime, to_date: datetime) -> list[dict[str, Any]]:
        """Fetch trades from source for a date range."""

    @abstractmethod
    def normalize_trade(self, raw_trade: dict[str, Any]) -> dict[str, Any]:
        """Normalize raw trade into unified schema."""

    def disconnect(self) -> None:
        """Optional connector cleanup."""

    def validate_trade(self, trade: dict[str, Any]) -> bool:
        required_fields = {'trade_date', 'symbol', 'quantity', 'price', 'side', 'source_trade_id', 'source_system'}
        return required_fields.issubset(trade.keys())
