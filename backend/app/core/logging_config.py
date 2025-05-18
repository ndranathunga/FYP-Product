import sys
from pathlib import Path
from loguru import logger


def setup_logging(logging_settings, project_root: Path):
    logger.remove()

    log_format = logging_settings.get(
        "format",
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    # Console Handler
    if logging_settings.get("console_enabled", True):
        logger.add(
            sys.stderr,  # Or sys.stdout
            level=logging_settings.get("console_level", "DEBUG").upper(),
            format=log_format,
            colorize=True,
        )
        logger.trace("Console logging enabled.")

    # File Handler
    if logging_settings.get("file_enabled", True):
        file_path_str = logging_settings.get("file_path", "logs/app.log")
        log_file_path = project_root / file_path_str

        # Ensure log directory exists
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_file_path,
            level=logging_settings.get("file_level", "INFO").upper(),
            rotation=logging_settings.get("rotation", "10 MB"),
            retention=logging_settings.get("retention", "7 days"),
            format=log_format,
            encoding="utf-8",
            enqueue=True,  # For async safety
            backtrace=True,  # Better tracebacks
            diagnose=True,  # More detailed error reporting
        )
        logger.trace(
            f"File logging enabled. Path: {log_file_path}, Level: {logging_settings.get('file_level', 'INFO').upper()}"
        )

    logger.trace(
        f"Logging setup complete. Global default level (for filtering if no handler matches): {logging_settings.get('level', 'INFO').upper()}"
    )
