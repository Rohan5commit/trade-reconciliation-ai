from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from src.models.database import BreakSeverity, BreakStatus, TradeBreak


class ExceptionRouter:
    """Rule-based intelligent routing for trade breaks."""

    def __init__(self, db: Session, config: dict[str, Any]):
        self.db = db
        self.routing_rules = self._load_routing_rules(config)

    @staticmethod
    def _load_routing_rules(_: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                'condition': lambda b: b.severity == BreakSeverity.CRITICAL,
                'assign_to': 'senior_ops_manager',
                'escalation_minutes': 15,
            },
            {
                'condition': lambda b: b.severity == BreakSeverity.HIGH and (b.pnl_impact or 0) and abs(b.pnl_impact) > 100_000,
                'assign_to': 'head_of_trading',
                'escalation_minutes': 30,
            },
            {
                'condition': lambda b: b.break_type == 'missing_trade',
                'assign_to': 'trade_support_team',
                'escalation_minutes': 60,
            },
            {
                'condition': lambda b: b.break_type in {'price_mismatch', 'quantity_mismatch'},
                'assign_to': 'ops_analyst',
                'escalation_minutes': 120,
            },
            {
                'condition': lambda b: True,
                'assign_to': 'ops_team',
                'escalation_minutes': 240,
            },
        ]

    def route_exception(self, break_id: int) -> dict[str, Any]:
        break_record = self.db.query(TradeBreak).filter(TradeBreak.id == break_id).first()
        if break_record is None:
            raise ValueError(f'Break {break_id} not found')

        for rule in self.routing_rules:
            if not rule['condition'](break_record):
                continue

            break_record.assigned_to = rule['assign_to']
            break_record.status = BreakStatus.IN_PROGRESS
            escalation_time = datetime.utcnow() + timedelta(minutes=rule['escalation_minutes'])
            self.db.commit()

            self._send_notification(break_record, rule['assign_to'])
            return {
                'break_id': break_record.id,
                'assigned_to': rule['assign_to'],
                'escalation_time': escalation_time,
            }

        raise RuntimeError('No routing rule matched')

    @staticmethod
    def _send_notification(break_record: TradeBreak, assignee: str) -> None:
        logger.info(f'Notification sent for break={break_record.id} assignee={assignee}')

    def check_sla_breaches(self) -> list[dict[str, Any]]:
        overdue_breaks = (
            self.db.query(TradeBreak)
            .filter(
                TradeBreak.status.in_([BreakStatus.OPEN, BreakStatus.IN_PROGRESS]),
                TradeBreak.sla_deadline.is_not(None),
                TradeBreak.sla_deadline < datetime.utcnow(),
            )
            .all()
        )

        escalated: list[dict[str, Any]] = []
        for break_record in overdue_breaks:
            original_assignee = break_record.assigned_to or 'unassigned'
            escalated_to = self._get_escalation_target(original_assignee)
            break_record.assigned_to = escalated_to
            break_record.status = BreakStatus.ESCALATED

            escalated.append(
                {
                    'break_id': break_record.id,
                    'original_assignee': original_assignee,
                    'escalated_to': escalated_to,
                }
            )

        if escalated:
            self.db.commit()

        return escalated

    @staticmethod
    def _get_escalation_target(current_assignee: str) -> str:
        escalation_map = {
            'ops_analyst': 'senior_ops_manager',
            'trade_support_team': 'ops_manager',
            'ops_team': 'ops_manager',
            'ops_manager': 'head_of_operations',
            'senior_ops_manager': 'head_of_operations',
        }
        return escalation_map.get(current_assignee, 'head_of_operations')
