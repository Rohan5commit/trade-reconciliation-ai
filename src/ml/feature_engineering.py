from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd


class BreakFeatureEngineer:
    """Feature extraction for break prediction."""

    @staticmethod
    def extract_features(trade: dict[str, Any], historical_data: pd.DataFrame | None = None) -> dict[str, float]:
        features: dict[str, float] = {}

        quantity = float(trade.get('quantity', 0) or 0)
        price = float(trade.get('price', 0) or 0)
        gross_amount = float(trade.get('gross_amount', quantity * price) or 0)
        commission = float(trade.get('commission', 0) or 0)

        features['quantity'] = quantity
        features['price'] = price
        features['gross_amount'] = gross_amount
        features['commission_pct'] = (commission / gross_amount * 100) if gross_amount else 0.0

        features['is_high_value'] = 1.0 if gross_amount > 1_000_000 else 0.0
        features['is_large_quantity'] = 1.0 if quantity > 10_000 else 0.0

        trade_date = trade.get('trade_date')
        if trade_date:
            parsed = trade_date if isinstance(trade_date, datetime) else pd.to_datetime(trade_date)
            features['day_of_week'] = float(parsed.weekday())
            features['hour_of_day'] = float(getattr(parsed, 'hour', 12))
            features['is_month_end'] = 1.0 if parsed.day >= 28 else 0.0
        else:
            features['day_of_week'] = 0.0
            features['hour_of_day'] = 12.0
            features['is_month_end'] = 0.0

        features['is_buy'] = 1.0 if str(trade.get('side', '')).upper() == 'BUY' else 0.0

        source = trade.get('source_system')
        cp = trade.get('counterparty')

        if historical_data is not None and not historical_data.empty:
            source_stats = historical_data[historical_data['source_system'] == source]
            features['source_break_rate'] = (
                float(source_stats['has_break'].mean()) if not source_stats.empty else 0.5
            )

            cp_stats = historical_data[historical_data['counterparty'] == cp]
            features['counterparty_break_rate'] = (
                float(cp_stats['has_break'].mean()) if not cp_stats.empty else 0.5
            )
        else:
            features['source_break_rate'] = 0.5
            features['counterparty_break_rate'] = 0.5

        return features
