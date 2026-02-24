from datetime import datetime

from src.matching.fuzzy_matcher import FuzzyMatcher


def test_fuzzy_matcher_exact_match_scores_high():
    matcher = FuzzyMatcher(
        {
            'AUTO_MATCH_THRESHOLD': 0.95,
            'MANUAL_REVIEW_THRESHOLD': 0.75,
            'PRICE_TOLERANCE_PCT': 0.01,
            'QUANTITY_TOLERANCE': 0,
        }
    )

    trade = {
        'symbol': 'AAPL',
        'trade_date': datetime(2026, 2, 24, 14, 30),
        'side': 'BUY',
        'quantity': 100,
        'price': 200.00,
        'counterparty': 'Goldman Sachs LLC',
    }

    score = matcher.compute_match_score(trade, trade.copy())
    assert score.overall_score >= 0.99
    assert score.is_match is True
    assert score.confidence_level == 'auto'


def test_fuzzy_matcher_detects_no_match_for_large_discrepancy():
    matcher = FuzzyMatcher(
        {
            'AUTO_MATCH_THRESHOLD': 0.95,
            'MANUAL_REVIEW_THRESHOLD': 0.75,
            'PRICE_TOLERANCE_PCT': 0.01,
            'QUANTITY_TOLERANCE': 0,
        }
    )

    t1 = {
        'symbol': 'AAPL',
        'trade_date': datetime(2026, 2, 24),
        'side': 'BUY',
        'quantity': 100,
        'price': 200,
        'counterparty': 'MS',
    }
    t2 = {
        'symbol': 'TSLA',
        'trade_date': datetime(2026, 2, 25),
        'side': 'SELL',
        'quantity': 400,
        'price': 310,
        'counterparty': 'Different',
    }

    score = matcher.compute_match_score(t1, t2)
    assert score.is_match is False
    assert score.confidence_level == 'no_match'
