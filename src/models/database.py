from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class TradeSource(str, enum.Enum):
    OMS = 'oms'
    CUSTODIAN = 'custodian'
    PRIME_BROKER = 'prime_broker'
    EXCHANGE = 'exchange'
    MANUAL_ENTRY = 'manual'


class BreakStatus(str, enum.Enum):
    OPEN = 'open'
    IN_PROGRESS = 'in_progress'
    RESOLVED = 'resolved'
    ESCALATED = 'escalated'
    ACCEPTED = 'accepted'


class BreakSeverity(str, enum.Enum):
    CRITICAL = 'critical'
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'


class Trade(Base):
    __tablename__ = 'trades'
    __table_args__ = (
        UniqueConstraint('source_system', 'source_trade_id', name='uq_trade_source_trade_id'),
    )

    id = Column(Integer, primary_key=True)

    source_system = Column(Enum(TradeSource), nullable=False)
    source_trade_id = Column(String(100), nullable=False)
    source_raw_data = Column(JSON)

    trade_date = Column(DateTime, nullable=False)
    settlement_date = Column(DateTime)

    symbol = Column(String(50), nullable=False)
    security_identifier = Column(String(50))

    side = Column(String(10), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    gross_amount = Column(Float)
    net_amount = Column(Float)

    currency = Column(String(10), default='USD')

    counterparty = Column(String(200))
    counterparty_normalized = Column(String(200))

    account_number = Column(String(100))
    portfolio = Column(String(100))

    commission = Column(Float, default=0.0)
    fees = Column(Float, default=0.0)

    is_matched = Column(Boolean, default=False)
    matched_trade_id = Column(Integer, ForeignKey('trades.id'), nullable=True)
    match_confidence = Column(Float)

    ingested_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    matched_trade = relationship('Trade', remote_side=[id], uselist=False, foreign_keys=[matched_trade_id])
    breaks = relationship('TradeBreak', back_populates='trade', foreign_keys='TradeBreak.trade_id')


class TradeBreak(Base):
    __tablename__ = 'trade_breaks'

    id = Column(Integer, primary_key=True)

    trade_id = Column(Integer, ForeignKey('trades.id'))
    matched_trade_id = Column(Integer, ForeignKey('trades.id'), nullable=True)

    break_type = Column(String(50), nullable=False)
    severity = Column(Enum(BreakSeverity), default=BreakSeverity.MEDIUM)

    field_name = Column(String(50))
    expected_value = Column(String(200))
    actual_value = Column(String(200))
    variance = Column(Float)
    variance_pct = Column(Float)

    pnl_impact = Column(Float)
    settlement_risk = Column(Boolean, default=False)

    status = Column(Enum(BreakStatus), default=BreakStatus.OPEN)
    assigned_to = Column(String(100))
    priority_score = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)
    sla_deadline = Column(DateTime)
    first_reviewed_at = Column(DateTime)
    resolved_at = Column(DateTime)

    resolution_notes = Column(Text)
    resolution_action = Column(String(100))
    root_cause = Column(String(200))
    resolved_by = Column(String(100))

    trade = relationship('Trade', foreign_keys=[trade_id], back_populates='breaks')
    matched_trade = relationship('Trade', foreign_keys=[matched_trade_id])
    comments = relationship('BreakComment', back_populates='break_record', cascade='all, delete-orphan')


class BreakComment(Base):
    __tablename__ = 'break_comments'

    id = Column(Integer, primary_key=True)
    break_id = Column(Integer, ForeignKey('trade_breaks.id'))

    user = Column(String(100), nullable=False)
    comment = Column(Text, nullable=False)
    action_taken = Column(String(100))

    created_at = Column(DateTime, default=datetime.utcnow)

    break_record = relationship('TradeBreak', back_populates='comments')


class MatchingRule(Base):
    __tablename__ = 'matching_rules'

    id = Column(Integer, primary_key=True)

    rule_name = Column(String(100), unique=True, nullable=False)
    rule_description = Column(Text)

    asset_class = Column(String(50), default='all')
    trade_type = Column(String(50), default='all')

    match_fields = Column(JSON)
    tolerance_rules = Column(JSON)

    priority = Column(Integer, default=100)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReconciliationRun(Base):
    __tablename__ = 'reconciliation_runs'

    id = Column(Integer, primary_key=True)

    run_date = Column(DateTime, nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)

    trade_date_from = Column(DateTime)
    trade_date_to = Column(DateTime)
    source_systems = Column(JSON)

    total_trades = Column(Integer, default=0)
    matched_trades = Column(Integer, default=0)
    breaks_identified = Column(Integer, default=0)
    auto_resolved = Column(Integer, default=0)
    manual_review_required = Column(Integer, default=0)

    duration_seconds = Column(Float)
    match_rate = Column(Float)

    status = Column(String(50), default='running')
    error_message = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)


class BreakPrediction(Base):
    __tablename__ = 'break_predictions'

    id = Column(Integer, primary_key=True)
    trade_id = Column(Integer, ForeignKey('trades.id'), nullable=False)

    prediction_score = Column(Float, nullable=False)
    predicted_break_type = Column(String(50))
    contributing_factors = Column(JSON)

    model_version = Column(String(50), nullable=False)
    predicted_at = Column(DateTime, default=datetime.utcnow)

    actual_break_occurred = Column(Boolean)
    validated_at = Column(DateTime)
