from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jellyfish
from rapidfuzz import fuzz


@dataclass
class MatchScore:
    overall_score: float
    field_scores: dict[str, float]
    is_match: bool
    confidence_level: str


class FuzzyMatcher:
    """Weighted fuzzy matching for cross-system trade reconciliation."""

    def __init__(self, config: dict[str, Any]):
        self.auto_match_threshold = float(config.get('AUTO_MATCH_THRESHOLD', 0.95))
        self.manual_review_threshold = float(config.get('MANUAL_REVIEW_THRESHOLD', 0.75))
        self.price_tolerance_pct = float(config.get('PRICE_TOLERANCE_PCT', 0.01))
        self.quantity_tolerance = float(config.get('QUANTITY_TOLERANCE', 0))

    def compute_match_score(
        self,
        trade1: dict[str, Any],
        trade2: dict[str, Any],
        weights: dict[str, float] | None = None,
    ) -> MatchScore:
        if weights is None:
            weights = {
                'symbol': 0.25,
                'trade_date': 0.15,
                'side': 0.15,
                'quantity': 0.2,
                'price': 0.15,
                'counterparty': 0.1,
            }

        field_scores: dict[str, float] = {
            'symbol': self._match_symbol(trade1.get('symbol'), trade2.get('symbol')),
            'trade_date': 1.0 if self._as_date(trade1.get('trade_date')) == self._as_date(trade2.get('trade_date')) else 0.0,
            'side': 1.0 if str(trade1.get('side', '')).upper() == str(trade2.get('side', '')).upper() else 0.0,
            'quantity': self._match_quantity(trade1.get('quantity'), trade2.get('quantity')),
            'price': self._match_price(trade1.get('price'), trade2.get('price')),
            'counterparty': self._match_counterparty(
                trade1.get('counterparty_normalized') or trade1.get('counterparty'),
                trade2.get('counterparty_normalized') or trade2.get('counterparty'),
            ),
        }

        overall_score = sum(field_scores[field] * weight for field, weight in weights.items())
        if overall_score >= self.auto_match_threshold:
            return MatchScore(overall_score, field_scores, True, 'auto')
        if overall_score >= self.manual_review_threshold:
            return MatchScore(overall_score, field_scores, True, 'review')
        return MatchScore(overall_score, field_scores, False, 'no_match')

    def find_best_match(
        self,
        source_trade: dict[str, Any],
        candidate_trades: list[dict[str, Any]],
        min_score: float | None = None,
    ) -> tuple[dict[str, Any] | None, MatchScore | None]:
        threshold = min_score if min_score is not None else self.manual_review_threshold
        best_match: dict[str, Any] | None = None
        best_score: MatchScore | None = None

        for candidate in candidate_trades:
            score = self.compute_match_score(source_trade, candidate)
            if score.overall_score < threshold:
                continue
            if best_score is None or score.overall_score > best_score.overall_score:
                best_match = candidate
                best_score = score

        return best_match, best_score

    @staticmethod
    def _as_date(value: Any) -> str:
        if value is None:
            return ''
        if hasattr(value, 'strftime'):
            return value.strftime('%Y-%m-%d')
        return str(value)[:10]

    @staticmethod
    def _match_symbol(sym1: str | None, sym2: str | None) -> float:
        if not sym1 or not sym2:
            return 0.0
        if sym1 == sym2:
            return 1.0
        similarity = fuzz.ratio(sym1, sym2) / 100.0
        return similarity if similarity >= 0.9 else 0.0

    def _match_quantity(self, qty1: float | None, qty2: float | None) -> float:
        if qty1 is None or qty2 is None:
            return 0.0
        diff = abs(float(qty1) - float(qty2))
        if diff <= self.quantity_tolerance:
            return 1.0
        denom = max(abs(float(qty1)), abs(float(qty2)), 1.0)
        pct_diff = diff / denom
        return max(0.0, 1.0 - pct_diff)

    def _match_price(self, price1: float | None, price2: float | None) -> float:
        if price1 is None or price2 is None:
            return 0.0
        if float(price1) == float(price2):
            return 1.0
        denom = max(abs(float(price1)), abs(float(price2)), 1e-9)
        pct_diff = abs(float(price1) - float(price2)) / denom
        if pct_diff <= self.price_tolerance_pct:
            return 1.0
        return max(0.0, 1.0 - (pct_diff / max(self.price_tolerance_pct, 1e-9)))

    @staticmethod
    def _match_counterparty(cp1: str | None, cp2: str | None) -> float:
        if not cp1 or not cp2:
            return 0.5
        if cp1 == cp2:
            return 1.0

        token_sort = fuzz.token_sort_ratio(cp1, cp2) / 100.0
        token_set = fuzz.token_set_ratio(cp1, cp2) / 100.0
        jaro = jellyfish.jaro_winkler_similarity(cp1, cp2)
        return token_sort * 0.4 + token_set * 0.4 + jaro * 0.2
