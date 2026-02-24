from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.ingestion.orchestrator import IngestionOrchestrator
from src.matching.orchestrator import MatchingOrchestrator
from src.ml.predictor import BreakPredictor
from src.models.database import BreakStatus, Trade, TradeBreak, TradeSource
from src.models.schemas import (
    BreakRouteResponse,
    BreakView,
    HealthResponse,
    IngestionRequest,
    ReconciliationRequest,
    ReconciliationStats,
    TradePredictionRequest,
    TradePredictionResponse,
)
from src.models.session import get_db
from src.reporting.analytics import ReportingService
from src.workflows.auto_remediation import AutoRemediator
from src.workflows.exception_router import ExceptionRouter
from src.workflows.root_cause import RootCauseAnalyzer

router = APIRouter(prefix='/api/v1', tags=['trade-reconciliation'])


def _settings_dict() -> dict[str, Any]:
    return get_settings().model_dump(by_alias=True)


def _predictor_or_none() -> BreakPredictor | None:
    settings = get_settings()
    model_path = Path(settings.ml_model_path) / settings.break_prediction_model
    if not model_path.exists():
        return None
    return BreakPredictor(str(model_path))


@router.get('/health', response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status='ok', timestamp=datetime.utcnow(), environment=settings.environment)


@router.post('/ingestion/run')
def run_ingestion(request: IngestionRequest, db: Session = Depends(get_db)) -> dict[str, int]:
    orchestrator = IngestionOrchestrator(db=db, config=_settings_dict())
    return orchestrator.ingest_all_sources(request.from_date, request.to_date)


@router.post('/reconciliation/run', response_model=ReconciliationStats)
def run_reconciliation(request: ReconciliationRequest, db: Session = Depends(get_db)) -> ReconciliationStats:
    stats = MatchingOrchestrator(db=db, config=_settings_dict()).run_reconciliation(
        trade_date=request.trade_date,
        source1=request.source1,
        source2=request.source2,
    )
    return ReconciliationStats(**stats)


@router.post('/exceptions/{break_id}/route', response_model=BreakRouteResponse)
def route_exception(break_id: int, db: Session = Depends(get_db)) -> BreakRouteResponse:
    try:
        routed = ExceptionRouter(db=db, config=_settings_dict()).route_exception(break_id)
        return BreakRouteResponse(**routed)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post('/exceptions/{break_id}/auto-remediate')
def auto_remediate(break_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    break_record = db.query(TradeBreak).filter(TradeBreak.id == break_id).first()
    if not break_record:
        raise HTTPException(status_code=404, detail=f'Break {break_id} not found')

    remediator = AutoRemediator()
    suggestion = remediator.suggest_action(break_record)

    applied = False
    if suggestion['auto_executable']:
        applied = remediator.apply_action(break_record, suggestion['action'])
        if applied:
            db.commit()

    return {'break_id': break_id, 'suggestion': suggestion, 'applied': applied}


@router.get('/exceptions/overdue')
def overdue_exceptions(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return ExceptionRouter(db=db, config=_settings_dict()).check_sla_breaches()


@router.get('/breaks/open', response_model=list[BreakView])
def list_open_breaks(db: Session = Depends(get_db)) -> list[BreakView]:
    breaks = (
        db.query(TradeBreak)
        .filter(TradeBreak.status.in_([BreakStatus.OPEN, BreakStatus.IN_PROGRESS, BreakStatus.ESCALATED]))
        .order_by(TradeBreak.created_at.desc())
        .all()
    )
    return [BreakView.model_validate(item) for item in breaks]


@router.get('/reports/summary')
def report_summary(db: Session = Depends(get_db)) -> dict[str, Any]:
    return ReportingService(db).summary()


@router.get('/reports/aging')
def report_aging(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return ReportingService(db).aging_report()


@router.get('/reports/runs')
def report_runs(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return ReportingService(db).run_history()


@router.get('/reports/root-cause')
def report_root_cause(db: Session = Depends(get_db)) -> dict[str, Any]:
    return RootCauseAnalyzer(db).summarize_patterns()


@router.post('/prediction/score', response_model=TradePredictionResponse)
def predict_break(request: TradePredictionRequest) -> TradePredictionResponse:
    predictor = _predictor_or_none()
    if predictor is None:
        raise HTTPException(status_code=404, detail='Model file not found. Train and save a model first.')

    prediction = predictor.predict_break_probability(request.trade)
    return TradePredictionResponse(**prediction)


@router.get('/trades/count')
def trade_count(db: Session = Depends(get_db)) -> dict[str, int]:
    count = db.query(Trade).count()
    return {'count': count}
