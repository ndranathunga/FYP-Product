import sys
from pathlib import Path


def get_api_base_url():
    try:
        PROJECT_ROOT = Path(__file__).resolve().parents[2]
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        from backend.app.config import settings as backend_settings

        api_host = backend_settings.backend.host
        if api_host == "0.0.0.0":
            api_host = "127.0.0.1"
        return f"http://{api_host}:{backend_settings.backend.port}/api/v1"
    except Exception:
        return "http://127.0.0.1:8000/api/v1"
