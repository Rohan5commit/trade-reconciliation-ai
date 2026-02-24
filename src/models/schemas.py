from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.models.database import BreakSeverity, BreakStatus, TradeSource


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    environment: str


class IngestionRequest(BaseModel):
    from_date: datetime
    to_date: datetime


class ReconciliationRequest(BaseModel):
    trade_date: datetime
    source1: TradeSource
    source2: TradeSource


class ReconciliationStats(BaseModel):
    auto_matched: int = 0
    manual_review: int = 0
    breaks_identified: int = 0
    unmatched_source1: int = 0
    unmatched_source2: int = 0


class BreakRouteResponse(BaseModel):
    break_id: int
    assigned_to: str
    escalation_time: datetime


class TradePredictionRequest(BaseModel):
    trade: dict[str, Any]


class TradePredictionResponse(BaseModel):
    break_probability: float = Field(ge=0.0, le=1.0)
    predicted_break: bool
    risk_level: str
    contributing_factors: dict[str, float]


class BreakView(BaseModel):
    id: int
    trade_id: int | None = None
    break_type: str
    severity: BreakSeverity
    status: BreakStatus
    assigned_to: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
