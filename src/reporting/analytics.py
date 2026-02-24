from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.database import BreakStatus, ReconciliationRun, Trade, TradeBreak


class ReportingService:
    """Aggregated metrics for dashboards and management reporting."""

    def __init__(self, db: Session):
        self.db = db

    def summary(self) -> dict[str, Any]:
        total_trades = self.db.query(func.count(Trade.id)).scalar() or 0
        total_breaks = self.db.query(func.count(TradeBreak.id)).scalar() or 0
        open_breaks = (
            self.db.query(func.count(TradeBreak.id))
            .filter(TradeBreak.status.in_([BreakStatus.OPEN, BreakStatus.IN_PROGRESS, BreakStatus.ESCALATED]))
            .scalar()
            or 0
        )
        resolved_breaks = (
            self.db.query(func.count(TradeBreak.id))
            .filter(TradeBreak.status == BreakStatus.RESOLVED)
            .scalar()
            or 0
        )

        match_rate = 0.0
        if total_trades:
            matched_trades = self.db.query(func.count(Trade.id)).filter(Trade.is_matched.is_(True)).scalar() or 0
            match_rate = matched_trades / total_trades

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'total_trades': int(total_trades),
            'total_breaks': int(total_breaks),
            'open_breaks': int(open_breaks),
            'resolved_breaks': int(resolved_breaks),
            'match_rate': round(match_rate, 4),
        }

    def aging_report(self) -> list[dict[str, Any]]:
        rows = (
            self.db.query(TradeBreak)
            .filter(TradeBreak.status.in_([BreakStatus.OPEN, BreakStatus.IN_PROGRESS, BreakStatus.ESCALATED]))
            .all()
        )
        now = datetime.utcnow()
        report: list[dict[str, Any]] = []
        for row in rows:
            age_hours = round((now - row.created_at).total_seconds() / 3600, 2)
            report.append(
                {
                    'break_id': row.id,
                    'break_type': row.break_type,
                    'status': row.status.value,
                    'severity': row.severity.value if row.severity else None,
                    'assigned_to': row.assigned_to,
                    'age_hours': age_hours,
                    'sla_deadline': row.sla_deadline.isoformat() if row.sla_deadline else None,
                }
            )
        return report

    def run_history(self, limit: int = 20) -> list[dict[str, Any]]:
        runs = self.db.query(ReconciliationRun).order_by(ReconciliationRun.created_at.desc()).limit(limit).all()
        return [
            {
                'id': run.id,
                'run_date': run.run_date.isoformat() if run.run_date else None,
                'status': run.status,
                'total_trades': run.total_trades,
                'matched_trades': run.matched_trades,
                'breaks_identified': run.breaks_identified,
                'match_rate': run.match_rate,
                'duration_seconds': run.duration_seconds,
                'error_message': run.error_message,
            }
            for run in runs
        ]
