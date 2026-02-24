from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import get_settings
from src.models.database import Base
from loguru import logger
import time

settings = get_settings()

engine = create_engine(settings.sqlalchemy_database_url, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)


def init_db(max_attempts: int = 10, delay_seconds: int = 2) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except OperationalError as exc:
            if attempt == max_attempts:
                logger.error(f'Database initialization failed after {max_attempts} attempts: {exc}')
                raise
            logger.warning(f'Database not ready (attempt {attempt}/{max_attempts}); retrying in {delay_seconds}s')
            time.sleep(delay_seconds)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
