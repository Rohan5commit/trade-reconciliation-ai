from __future__ import annotations

import re
from datetime import datetime


class FieldNormalizer:
    """Normalize fields prior to fuzzy matching."""

    @staticmethod
    def normalize_symbol(symbol: str | None) -> str:
        if not symbol:
            return ''
        normalized = symbol.upper().strip()
        normalized = re.sub(r'\.[A-Z]{1,4}$', '', normalized)
        return normalized.replace(' ', '')

    @staticmethod
    def normalize_counterparty(counterparty: str | None) -> str:
        if not counterparty:
            return ''

        text = counterparty.upper().strip()
        suffixes = [
            'INC',
            'INCORPORATED',
            'LLC',
            'LTD',
            'LIMITED',
            'CORP',
            'CORPORATION',
            'CO',
            'LP',
            'LLP',
            'PLC',
            'SA',
            'AG',
            'GMBH',
            'NV',
            'BV',
        ]
        for suffix in suffixes:
            text = re.sub(rf'\b{suffix}\b\.?', '', text)

        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @staticmethod
    def normalize_amount(amount: float | None, decimals: int = 2) -> float:
        return round(float(amount or 0), decimals)

    @staticmethod
    def normalize_date(date_obj: datetime | None) -> str:
        if date_obj is None:
            return ''
        return date_obj.strftime('%Y-%m-%d')
