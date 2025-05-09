import json
import joblib
from pathlib import Path
from typing import Any, Optional

from ..config import settings

def save_cache(data: Any, file_name: str):
    cache_path = Path(settings.backend.cache_dir) / file_name
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True) # Ensure dir exists
        if isinstance(data, (dict, list)) and file_name.endswith(".json"):
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        else:
            joblib.dump(data, cache_path)
        print(f"Data cached successfully to {cache_path}")
    except Exception as e:
        print(f"Error saving cache to {cache_path}: {e}")

def load_cache(file_name: str) -> Optional[Any]:
    cache_path = Path(settings.backend.cache_dir) / file_name
    if cache_path.exists():
        try:
            if file_name.endswith(".json"):
                 with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = joblib.load(cache_path)
            print(f"Data loaded successfully from cache {cache_path}")
            return data
        except Exception as e:
            print(f"Error loading cache from {cache_path}: {e}. Invalidating cache.")
            try: cache_path.unlink() # Remove corrupted cache
            except OSError as oe: print(f"Error removing corrupted cache file {cache_path}: {oe}")
            return None
    return None
