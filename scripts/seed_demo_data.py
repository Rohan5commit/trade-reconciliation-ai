from __future__ import annotations

from datetime import datetime

from src.models.database import Trade, TradeSource
from src.models.session import SessionLocal, init_db


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        seed_trades = [
            Trade(
                source_system=TradeSource.OMS,
                source_trade_id='OMS_DEMO_001',
                trade_date=datetime.utcnow(),
                symbol='AAPL',
                side='BUY',
                quantity=150,
                price=199.10,
                counterparty='Goldman Sachs LLC',
                account_number='ACC-001',
            ),
            Trade(
                source_system=TradeSource.CUSTODIAN,
                source_trade_id='CUS_DEMO_001',
                trade_date=datetime.utcnow(),
                symbol='AAPL',
                side='BUY',
                quantity=150,
                price=199.11,
                counterparty='Goldman Sachs',
                account_number='ACC-001',
            ),
        ]

        db.add_all(seed_trades)
        db.commit()
        print(f'Seeded {len(seed_trades)} demo trades')
    finally:
        db.close()


if __name__ == '__main__':
    main()
