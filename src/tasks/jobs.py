from __future__ import annotations

from datetime import datetime, timedelta
from time import perf_counter

from loguru import logger

from src.config.settings import get_settings
from src.ingestion.orchestrator import IngestionOrchestrator
from src.matching.orchestrator import MatchingOrchestrator
from src.models.database import ReconciliationRun, TradeSource
from src.models.session import SessionLocal
from src.tasks.worker import celery_app
from src.workflows.exception_router import ExceptionRouter


def _settings_dict() -> dict[str, str]:
    return get_settings().model_dump(by_alias=True)


@celery_app.task(name='tasks.run_ingestion')
def run_ingestion(from_date_iso: str, to_date_iso: str) -> dict[str, int]:
    from_date = datetime.fromisoformat(from_date_iso)
    to_date = datetime.fromisoformat(to_date_iso)

    db = SessionLocal()
    try:
        orchestrator = IngestionOrchestrator(db=db, config=_settings_dict())
        return orchestrator.ingest_all_sources(from_date=from_date, to_date=to_date)
    finally:
        db.close()


@celery_app.task(name='tasks.run_reconciliation')
def run_reconciliation(trade_date_iso: str, source1: str, source2: str) -> dict[str, int]:
    trade_date = datetime.fromisoformat(trade_date_iso)

    db = SessionLocal()
    run = ReconciliationRun(
        run_date=trade_date,
        trade_date_from=trade_date,
        trade_date_to=trade_date,
        source_systems=[source1, source2],
        status='running',
    )
    start = perf_counter()
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        stats = MatchingOrchestrator(db=db, config=_settings_dict()).run_reconciliation(
            trade_date=trade_date,
            source1=TradeSource(source1),
            source2=TradeSource(source2),
        )
        duration = perf_counter() - start

        total = stats['auto_matched'] + stats['manual_review'] + stats['unmatched_source1'] + stats['unmatched_source2']
        run.total_trades = total
        run.matched_trades = stats['auto_matched'] + stats['manual_review']
        run.breaks_identified = stats['breaks_identified']
        run.manual_review_required = stats['manual_review']
        run.duration_seconds = duration
        run.match_rate = (run.matched_trades / total) if total else 0
        run.status = 'completed'
        run.end_time = datetime.utcnow()
        db.commit()

        return stats
    except Exception as exc:
        logger.exception('Reconciliation task failed')
        run.status = 'failed'
        run.error_message = str(exc)
        run.end_time = datetime.utcnow()
        db.commit()
        raise
    finally:
        db.close()


@celery_app.task(name='tasks.check_sla_breaches')
def check_sla_breaches() -> list[dict[str, str]]:
    db = SessionLocal()
    try:
        return ExceptionRouter(db=db, config=_settings_dict()).check_sla_breaches()
    finally:
        db.close()


@celery_app.task(name='tasks.daily_pipeline')
def daily_pipeline() -> dict[str, object]:
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)

    ingestion = run_ingestion(yesterday.isoformat(), today.isoformat())
    reconciliation = run_reconciliation(yesterday.isoformat(), TradeSource.OMS.value, TradeSource.CUSTODIAN.value)

    return {
        'ingestion': ingestion,
        'reconciliation': reconciliation,
        'window': {'from': yesterday.isoformat(), 'to': today.isoformat()},
    }
