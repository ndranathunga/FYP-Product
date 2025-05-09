import uvicorn
import sys
from pathlib import Path
from loguru import logger

PROJECT_ROOT_PATH = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_PATH))

try:
    from backend.app.config import settings

    logger.info(
        "Successfully imported settings in run.py, logging should be configured."
    )
except Exception as e:
    logger.remove()
    logger.add(sys.stderr, level="ERROR")
    logger.critical(
        f"RUN.PY: Failed to import settings or setup logging: {e}", exc_info=True
    )
    sys.exit(
        "Critical error: Could not initialize application configuration or logging."
    )


if __name__ == "__main__":
    logger.info(
        f"Starting Uvicorn server on {settings.backend.host}:{settings.backend.port}"
    )
    logger.debug(f"Frontend base URL from settings: {settings.frontend_base_url}")
    logger.debug(f"Full settings dump: {settings.model_dump_json(indent=2)}")

    uvicorn.run(
        "backend.app.main:app",
        host=settings.backend.host,
        port=settings.backend.port,
        reload=True,
        reload_dirs=[str(PROJECT_ROOT_PATH)],
        log_level=settings.logging.level.lower(),
    )
