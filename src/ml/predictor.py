from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from loguru import logger

from src.ml.feature_engineering import BreakFeatureEngineer


class BreakPredictor:
    """Real-time inference for break probability."""

    def __init__(self, model_path: str):
        model_obj = joblib.load(model_path)
        if isinstance(model_obj, dict) and 'model' in model_obj:
            self.model = model_obj['model']
            self.feature_names = model_obj.get('feature_names', [])
        else:
            self.model = model_obj
            self.feature_names = []

        self.feature_engineer = BreakFeatureEngineer()
        logger.info(f'Loaded break prediction model from {model_path}')

    @classmethod
    def from_default_path(cls, base_path: str, filename: str) -> 'BreakPredictor | None':
        target = Path(base_path) / filename
        if not target.exists():
            return None
        return cls(str(target))

    def predict_break_probability(
        self,
        trade: dict[str, Any],
        historical_data: pd.DataFrame | None = None,
    ) -> dict[str, Any]:
        features = self.feature_engineer.extract_features(trade, historical_data)
        features_df = pd.DataFrame([features]).fillna(0)

        if self.feature_names:
            for feature in self.feature_names:
                if feature not in features_df.columns:
                    features_df[feature] = 0.0
            features_df = features_df[self.feature_names]

        probability = float(self.model.predict_proba(features_df)[0, 1])
        predicted_break = probability >= 0.5

        top_factors: dict[str, float] = {}
        feature_importance = getattr(self.model, 'feature_importances_', None)
        if feature_importance is not None:
            names = self.feature_names or list(features_df.columns)
            ranked = sorted(zip(names, feature_importance), key=lambda x: abs(float(x[1])), reverse=True)[:5]
            top_factors = {name: float(value) for name, value in ranked}

        return {
            'break_probability': probability,
            'predicted_break': bool(predicted_break),
            'contributing_factors': top_factors,
            'risk_level': self._assess_risk_level(probability),
        }

    @staticmethod
    def _assess_risk_level(probability: float) -> str:
        if probability >= 0.8:
            return 'critical'
        if probability >= 0.6:
            return 'high'
        if probability >= 0.4:
            return 'medium'
        return 'low'
