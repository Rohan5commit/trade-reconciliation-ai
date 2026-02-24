from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.matching.fuzzy_matcher import FuzzyMatcher
from src.matching.normalizers import FieldNormalizer
from src.models.database import BreakSeverity, BreakStatus, Trade, TradeBreak, TradeSource


class MatchingOrchestrator:
    """Runs reconciliation between two trade sources."""

    def __init__(self, db: Session, config: dict[str, Any]):
        self.db = db
        self.matcher = FuzzyMatcher(config)
        self.normalizer = FieldNormalizer()

    def run_reconciliation(self, trade_date: datetime, source1: TradeSource, source2: TradeSource) -> dict[str, int]:
        logger.info(f'Starting reconciliation {source1.value} vs {source2.value} for {trade_date.date()}')

        trades1 = self._fetch_unmatched_trades(source1, trade_date)
        trades2 = self._fetch_unmatched_trades(source2, trade_date)

        for trade in trades1 + trades2:
            self._normalize_trade_fields(trade)

        stats = {
            'auto_matched': 0,
            'manual_review': 0,
            'breaks_identified': 0,
            'unmatched_source1': 0,
            'unmatched_source2': 0,
        }

        matched_ids2: set[int] = set()

        for trade1 in trades1:
            candidates = [self._trade_to_dict(t) for t in trades2 if t.id not in matched_ids2]
            best_match, score = self.matcher.find_best_match(self._trade_to_dict(trade1), candidates)

            if not best_match or score is None:
                continue

            trade2 = next(t for t in trades2 if t.id == best_match['id'])
            self._set_match_pair(trade1, trade2, score.overall_score)
            matched_ids2.add(trade2.id)

            if score.confidence_level == 'auto':
                stats['auto_matched'] += 1
            else:
                stats['manual_review'] += 1

            for break_data in self._identify_breaks(trade1, trade2, score.field_scores):
                self.db.add(TradeBreak(**break_data))
                stats['breaks_identified'] += 1

        for trade1 in trades1:
            if not trade1.is_matched:
                self._create_missing_trade_break(trade1, source2)
                stats['unmatched_source1'] += 1

        for trade2 in trades2:
            if not trade2.is_matched:
                self._create_missing_trade_break(trade2, source1)
                stats['unmatched_source2'] += 1

        self.db.commit()
        logger.info(f'Reconciliation complete: {stats}')
        return stats

    def _fetch_unmatched_trades(self, source: TradeSource, trade_date: datetime) -> list[Trade]:
        start = trade_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return (
            self.db.query(Trade)
            .filter(
                and_(
                    Trade.source_system == source,
                    Trade.trade_date >= start,
                    Trade.trade_date < end,
                    Trade.is_matched.is_(False),
                )
            )
            .all()
        )

    def _normalize_trade_fields(self, trade: Trade) -> None:
        trade.symbol = self.normalizer.normalize_symbol(trade.symbol)
        if trade.counterparty and not trade.counterparty_normalized:
            trade.counterparty_normalized = self.normalizer.normalize_counterparty(trade.counterparty)

    @staticmethod
    def _trade_to_dict(trade: Trade) -> dict[str, Any]:
        return {
            'id': trade.id,
            'symbol': trade.symbol,
            'trade_date': trade.trade_date,
            'side': trade.side,
            'quantity': trade.quantity,
            'price': trade.price,
            'counterparty': trade.counterparty,
            'counterparty_normalized': trade.counterparty_normalized,
        }

    @staticmethod
    def _set_match_pair(trade1: Trade, trade2: Trade, confidence: float) -> None:
        trade1.is_matched = True
        trade1.matched_trade_id = trade2.id
        trade1.match_confidence = confidence

        trade2.is_matched = True
        trade2.matched_trade_id = trade1.id
        trade2.match_confidence = confidence

    def _identify_breaks(self, trade1: Trade, trade2: Trade, field_scores: dict[str, float]) -> list[dict[str, Any]]:
        breaks: list[dict[str, Any]] = []
        for field, score in field_scores.items():
            if score >= 0.99:
                continue

            val1 = getattr(trade1, field, None)
            val2 = getattr(trade2, field, None)
            if val1 == val2:
                continue

            variance = None
            variance_pct = None
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                variance = abs(float(val1) - float(val2))
                denom = max(abs(float(val1)), abs(float(val2)), 1.0)
                variance_pct = (variance / denom) * 100

            severity = self._assess_break_severity(field, variance, variance_pct)
            breaks.append(
                {
                    'trade_id': trade1.id,
                    'matched_trade_id': trade2.id,
                    'break_type': f'{field}_mismatch',
                    'severity': severity,
                    'field_name': field,
                    'expected_value': str(val1),
                    'actual_value': str(val2),
                    'variance': variance,
                    'variance_pct': variance_pct,
                    'status': BreakStatus.OPEN,
                    'sla_deadline': self._calculate_sla_deadline(severity),
                    'priority_score': 1.0 - score,
                }
            )
        return breaks

    @staticmethod
    def _assess_break_severity(field: str, variance: float | None, variance_pct: float | None) -> BreakSeverity:
        if field in {'quantity', 'side'} and (variance is None or variance > 0):
            return BreakSeverity.CRITICAL
        if field == 'price':
            return BreakSeverity.HIGH if variance_pct and variance_pct > 1.0 else BreakSeverity.MEDIUM
        if field in {'gross_amount', 'net_amount'}:
            return BreakSeverity.MEDIUM
        return BreakSeverity.LOW

    @staticmethod
    def _calculate_sla_deadline(severity: BreakSeverity) -> datetime:
        if severity == BreakSeverity.CRITICAL:
            minutes = int(os.getenv('SLA_HIGH_PRIORITY', '30'))
        elif severity == BreakSeverity.HIGH:
            minutes = int(os.getenv('SLA_MEDIUM_PRIORITY', '120'))
        else:
            minutes = int(os.getenv('SLA_LOW_PRIORITY', '480'))
        return datetime.utcnow() + timedelta(minutes=minutes)

    def _create_missing_trade_break(self, trade: Trade, expected_source: TradeSource) -> None:
        self.db.add(
            TradeBreak(
                trade_id=trade.id,
                break_type='missing_trade',
                severity=BreakSeverity.HIGH,
                field_name='trade_existence',
                expected_value=f'Trade in {expected_source.value}',
                actual_value='Not found',
                status=BreakStatus.OPEN,
                sla_deadline=self._calculate_sla_deadline(BreakSeverity.HIGH),
            )
        )
