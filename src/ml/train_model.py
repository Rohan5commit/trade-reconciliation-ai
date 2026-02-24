from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from imblearn.over_sampling import SMOTE
from loguru import logger
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

try:
    from xgboost import XGBClassifier
except ImportError:  # pragma: no cover - optional runtime dependency
    XGBClassifier = None


class BreakPredictionTrainer:
    """Model training utility for break prediction."""

    def __init__(self, model_path: str = './models'):
        self.model_path = Path(model_path)
        self.model_path.mkdir(parents=True, exist_ok=True)
        self.model: Any | None = None
        self.feature_names: list[str] | None = None

    @staticmethod
    def prepare_training_data(trades_df: pd.DataFrame, breaks_df: pd.DataFrame) -> pd.DataFrame:
        labeled = trades_df.copy()
        labeled['has_break'] = labeled['id'].isin(breaks_df['trade_id'].unique()).astype(int)
        logger.info(
            f'Training rows={len(labeled)} breaks={int(labeled["has_break"].sum())} break_rate={labeled["has_break"].mean():.2%}'
        )
        return labeled

    def train(self, training_data: pd.DataFrame, target_col: str = 'has_break') -> dict[str, Any]:
        if target_col not in training_data.columns:
            raise ValueError(f'Missing target column: {target_col}')

        exclude_cols = {target_col, 'id', 'trade_date', 'symbol', 'source_system', 'counterparty'}
        feature_cols = [col for col in training_data.columns if col not in exclude_cols]

        X = training_data[feature_cols].fillna(0)
        y = training_data[target_col]

        if y.nunique() < 2:
            raise ValueError('Training target has only one class; cannot train classifier')

        self.feature_names = feature_cols

        X_resampled, y_resampled = SMOTE(random_state=42).fit_resample(X, y)

        X_train, X_test, y_train, y_test = train_test_split(
            X_resampled,
            y_resampled,
            test_size=0.2,
            random_state=42,
            stratify=y_resampled,
        )

        if XGBClassifier is not None:
            self.model = XGBClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                eval_metric='logloss',
            )
        else:
            self.model = GradientBoostingClassifier(random_state=42)

        self.model.fit(X_train, y_train)

        y_pred = self.model.predict(X_test)
        y_prob = self.model.predict_proba(X_test)[:, 1]

        accuracy = float((y_pred == y_test).mean())
        auc = float(roc_auc_score(y_test, y_prob))

        logger.info(f'Accuracy={accuracy:.3f} ROC_AUC={auc:.3f}')
        logger.info('\n' + classification_report(y_test, y_pred))

        feature_importance = getattr(self.model, 'feature_importances_', None)
        importance_df = pd.DataFrame(
            {
                'feature': feature_cols,
                'importance': feature_importance if feature_importance is not None else [0.0] * len(feature_cols),
            }
        ).sort_values('importance', ascending=False)

        model_file = self.model_path / f'break_predictor_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.pkl'
        joblib.dump({'model': self.model, 'feature_names': self.feature_names}, model_file)

        return {
            'accuracy': accuracy,
            'auc': auc,
            'model_file': str(model_file),
            'feature_importance': importance_df.to_dict('records'),
        }

    def predict(self, trade_features: pd.DataFrame) -> pd.DataFrame:
        if self.model is None or self.feature_names is None:
            raise ValueError('Model not trained. Call train() first.')

        X = trade_features[self.feature_names].fillna(0)
        probabilities = self.model.predict_proba(X)[:, 1]

        output = trade_features.copy()
        output['break_probability'] = probabilities
        output['predicted_break'] = (probabilities >= 0.5).astype(int)
        return output
