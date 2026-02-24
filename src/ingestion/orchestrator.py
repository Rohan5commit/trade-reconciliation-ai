from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.ingestion.custodian_connector import CustodianConnector
from src.ingestion.oms_connector import OMSConnector
from src.models.database import Trade, TradeSource


class IngestionOrchestrator:
    """Coordinates trade ingestion from all configured sources."""

    def __init__(self, db: Session, config: dict[str, Any]):
        self.db = db
        self.connectors = {
            TradeSource.OMS: OMSConnector(config),
            TradeSource.CUSTODIAN: CustodianConnector(config),
        }

    def ingest_all_sources(self, from_date: datetime, to_date: datetime) -> dict[str, int]:
        results: dict[str, int] = {}

        for source, connector in self.connectors.items():
            saved_count = 0
            try:
                logger.info(f'Ingesting from {source.value}')
                if not connector.connect():
                    results[source.value] = 0
                    continue

                raw_trades = connector.fetch_trades(from_date, to_date)
                for raw_trade in raw_trades:
                    try:
                        normalized = connector.normalize_trade(raw_trade)
                        if not connector.validate_trade(normalized):
                            continue

                        exists = (
                            self.db.query(Trade)
                            .filter(
                                Trade.source_system == source,
                                Trade.source_trade_id == normalized['source_trade_id'],
                            )
                            .first()
                        )
                        if exists:
                            continue

                        self.db.add(Trade(**normalized))
                        saved_count += 1
                    except Exception as exc:
                        logger.error(f'Normalization failed for {source.value} trade: {exc}')

                self.db.commit()
                results[source.value] = saved_count
                logger.info(f'Saved {saved_count} trades from {source.value}')
            except SQLAlchemyError:
                self.db.rollback()
                logger.exception(f'Database error ingesting from {source.value}')
                results[source.value] = 0
            except Exception:
                logger.exception(f'Ingestion error for source {source.value}')
                results[source.value] = 0
            finally:
                connector.disconnect()

        return results
