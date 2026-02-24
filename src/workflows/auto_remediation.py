from __future__ import annotations

from typing import Any

from src.models.database import BreakStatus, TradeBreak


class AutoRemediator:
    """Suggests and applies low-risk remediation actions."""

    def suggest_action(self, break_record: TradeBreak) -> dict[str, Any]:
        if break_record.break_type == 'missing_trade':
            return {
                'action': 'request_missing_trade_resend',
                'auto_executable': False,
                'reason': 'Requires external source confirmation',
            }
        if break_record.break_type == 'counterparty_mismatch':
            return {
                'action': 'normalize_counterparty_alias',
                'auto_executable': True,
                'reason': 'Likely naming standardization issue',
            }
        if break_record.break_type == 'price_mismatch' and break_record.variance_pct is not None and break_record.variance_pct < 0.1:
            return {
                'action': 'accept_minor_price_rounding',
                'auto_executable': True,
                'reason': 'Within acceptable micro-tolerance',
            }

        return {
            'action': 'manual_investigation',
            'auto_executable': False,
            'reason': 'No safe automated path',
        }

    def apply_action(self, break_record: TradeBreak, action: str, actor: str = 'system') -> bool:
        if action == 'accept_minor_price_rounding':
            break_record.status = BreakStatus.RESOLVED
            break_record.resolution_action = action
            break_record.resolution_notes = 'Automatically accepted minor price variance'
            break_record.resolved_by = actor
            return True

        if action == 'normalize_counterparty_alias':
            break_record.status = BreakStatus.IN_PROGRESS
            break_record.resolution_action = action
            break_record.resolution_notes = 'Alias normalization queued for reference data update'
            return True

        return False
