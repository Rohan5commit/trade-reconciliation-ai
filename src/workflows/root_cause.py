from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from src.models.database import TradeBreak


class RootCauseAnalyzer:
    """Simple pattern mining over historical breaks."""

    def __init__(self, db: Session):
        self.db = db

    def summarize_patterns(self, limit: int = 10) -> dict[str, Any]:
        breaks = self.db.query(TradeBreak).all()
        if not breaks:
            return {'top_break_types': [], 'top_fields': [], 'top_assignees': []}

        break_type_counts = Counter(b.break_type for b in breaks if b.break_type)
        field_counts = Counter(b.field_name for b in breaks if b.field_name)
        assignee_counts = Counter(b.assigned_to for b in breaks if b.assigned_to)

        return {
            'top_break_types': break_type_counts.most_common(limit),
            'top_fields': field_counts.most_common(limit),
            'top_assignees': assignee_counts.most_common(limit),
        }
