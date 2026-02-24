from __future__ import annotations

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
        case_sensitive=False,
    )

    postgres_host: str = Field(default='localhost', alias='POSTGRES_HOST')
    postgres_port: int = Field(default=5432, alias='POSTGRES_PORT')
    postgres_db: str = Field(default='trade_recon', alias='POSTGRES_DB')
    postgres_user: str = Field(default='postgres', alias='POSTGRES_USER')
    postgres_password: str = Field(default='', alias='POSTGRES_PASSWORD')
    database_url: str | None = Field(default=None, alias='DATABASE_URL')

    redis_url: str = Field(default='redis://localhost:6379/0', alias='REDIS_URL')

    oms_api_url: str = Field(default='', alias='OMS_API_URL')
    oms_api_key: str = Field(default='', alias='OMS_API_KEY')
    custodian_sftp_host: str = Field(default='', alias='CUSTODIAN_SFTP_HOST')
    custodian_sftp_user: str = Field(default='', alias='CUSTODIAN_SFTP_USER')
    custodian_sftp_key: str = Field(default='', alias='CUSTODIAN_SFTP_KEY')
    prime_broker_api_url: str = Field(default='', alias='PRIME_BROKER_API_URL')
    prime_broker_api_key: str = Field(default='', alias='PRIME_BROKER_API_KEY')

    ml_model_path: str = Field(default='./models', alias='ML_MODEL_PATH')
    break_prediction_model: str = Field(default='break_predictor_latest.pkl', alias='BREAK_PREDICTION_MODEL')

    fuzzy_match_threshold: float = Field(default=0.85, alias='FUZZY_MATCH_THRESHOLD')
    auto_match_threshold: float = Field(default=0.95, alias='AUTO_MATCH_THRESHOLD')
    manual_review_threshold: float = Field(default=0.75, alias='MANUAL_REVIEW_THRESHOLD')
    price_tolerance_pct: float = Field(default=0.01, alias='PRICE_TOLERANCE_PCT')
    quantity_tolerance: float = Field(default=0.0, alias='QUANTITY_TOLERANCE')

    sla_high_priority: int = Field(default=30, alias='SLA_HIGH_PRIORITY')
    sla_medium_priority: int = Field(default=120, alias='SLA_MEDIUM_PRIORITY')
    sla_low_priority: int = Field(default=480, alias='SLA_LOW_PRIORITY')

    email_smtp_host: str = Field(default='', alias='EMAIL_SMTP_HOST')
    email_smtp_port: int = Field(default=587, alias='EMAIL_SMTP_PORT')
    email_user: str = Field(default='', alias='EMAIL_USER')
    email_password: str = Field(default='', alias='EMAIL_PASSWORD')
    slack_webhook_url: str = Field(default='', alias='SLACK_WEBHOOK_URL')

    log_level: str = Field(default='INFO', alias='LOG_LEVEL')
    environment: str = Field(default='development', alias='ENVIRONMENT')
    max_workers: int = Field(default=8, alias='MAX_WORKERS')

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        if self.environment.lower() == 'test':
            return 'sqlite+pysqlite:///:memory:'
        password = self.postgres_password or 'change_me'
        return (
            f'postgresql+psycopg2://{self.postgres_user}:{password}'
            f'@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}'
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
