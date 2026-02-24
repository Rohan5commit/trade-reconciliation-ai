from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.matching.orchestrator import MatchingOrchestrator
from src.models.database import Base, Trade, TradeSource


def test_reconciliation_matches_simple_pair():
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        t1 = Trade(
            source_system=TradeSource.OMS,
            source_trade_id='oms-1',
            trade_date=datetime(2026, 2, 24, 10, 0),
            symbol='AAPL',
            side='BUY',
            quantity=100,
            price=200.0,
            counterparty='Goldman Sachs LLC',
        )
        t2 = Trade(
            source_system=TradeSource.CUSTODIAN,
            source_trade_id='cust-1',
            trade_date=datetime(2026, 2, 24, 10, 0),
            symbol='AAPL',
            side='BUY',
            quantity=100,
            price=200.0,
            counterparty='Goldman Sachs',
        )
        db.add_all([t1, t2])
        db.commit()

        stats = MatchingOrchestrator(
            db=db,
            config={
                'AUTO_MATCH_THRESHOLD': 0.95,
                'MANUAL_REVIEW_THRESHOLD': 0.75,
                'PRICE_TOLERANCE_PCT': 0.01,
                'QUANTITY_TOLERANCE': 0,
            },
        ).run_reconciliation(
            trade_date=datetime(2026, 2, 24),
            source1=TradeSource.OMS,
            source2=TradeSource.CUSTODIAN,
        )

        assert stats['auto_matched'] == 1
        assert stats['unmatched_source1'] == 0
        assert stats['unmatched_source2'] == 0
