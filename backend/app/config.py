import yaml
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

from backend.app.core.logging_config import setup_logging  


class ModelConfig(BaseModel):
    type: str
    class_name: Optional[str] = Field(None, alias="class")
    endpoint: Optional[str] = None
    api_key: Optional[str] = None


class ModelsConfig(BaseModel):
    sentiment: ModelConfig
    language: ModelConfig


class PromptsEngineConfig(BaseModel):
    template_dir: str
    default_version: str


class PromptsConfig(BaseModel):
    engine: PromptsEngineConfig


class LoggingConfig(BaseModel): 
    level: str = "INFO"
    console_enabled: bool = True
    console_level: str = "DEBUG"
    file_enabled: bool = True
    file_path: str = "logs/app.log"
    file_level: str = "INFO"
    rotation: str = "10 MB"
    retention: str = "7 days"
    format: str = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
    )


class BackendConfig(BaseModel):
    host: str
    port: int
    cache_dir: str
    dataset_path: str
    results_cache_file: str
    force_reanalyze_on_startup: bool = False


class Settings(BaseModel):
    backend: BackendConfig
    models: ModelsConfig
    prompts: PromptsConfig
    frontend_base_url: str
    logging: LoggingConfig 


def load_config() -> Settings:
    config_file_path = PROJECT_ROOT / "config" / "settings.yaml"

    with open(config_file_path, "r") as f:
        config_data = yaml.safe_load(f)

    config_data["backend"]["cache_dir"] = str(
        PROJECT_ROOT / config_data["backend"]["cache_dir"]
    )
    config_data["backend"]["dataset_path"] = str(
        PROJECT_ROOT / config_data["backend"]["dataset_path"]
    )
    config_data["prompts"]["engine"]["template_dir"] = str(
        PROJECT_ROOT / config_data["prompts"]["engine"]["template_dir"]
    )

    loaded_settings = Settings(**config_data)

    setup_logging(loaded_settings.logging.model_dump(), PROJECT_ROOT)

    return loaded_settings


settings = load_config()  

# Ensure cache directory exists at runtime
Path(settings.backend.cache_dir).mkdir(parents=True, exist_ok=True)

# TODO: Remove this after testing
from loguru import logger

logger.debug(f"Configuration loaded. Project Root: {PROJECT_ROOT}")
logger.info(f"Frontend base URL configured: {settings.frontend_base_url}")
