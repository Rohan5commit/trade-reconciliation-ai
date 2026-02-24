from loguru import logger


def configure_logging(level: str = 'INFO') -> None:
    logger.remove()
    logger.add(
        sink=lambda msg: print(msg, end=''),
        level=level.upper(),
        format='{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}',
    )
