import json
from pathlib import Path
from typing import Dict, Optional
from loguru import logger

from ..config import settings


class PromptEngine:
    def __init__(self, template_dir: str, default_version: str):
        self.template_dir = Path(template_dir)
        self.default_version = default_version
        self.prompts_cache: Dict[str, Dict] = {}
        self._load_all_prompts()

    def _load_all_prompts(self):
        if not self.template_dir.is_dir():
            logger.warning(
                f"Prompt template directory not found or not a directory: {self.template_dir}"
            )
            return
        for file_path in self.template_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    prompt_data = json.load(f)
                prompt_name_from_file = file_path.stem
                version = prompt_data.get("version", self.default_version)
                base_name = prompt_data.get(
                    "name", prompt_name_from_file.replace(f"_{version}", "")
                )

                key = (
                    f"{base_name}_{version}"
                    if "name" in prompt_data
                    else prompt_name_from_file
                )
                self.prompts_cache[key] = prompt_data
                logger.debug(f"Loaded prompt: {key} from {file_path.name}")
            except json.JSONDecodeError:
                logger.warning(f"Could not decode JSON from {file_path}", exc_info=True)
            except Exception as e:
                logger.warning(f"Error loading prompt {file_path}: {e}", exc_info=True)

    def get_prompt(
        self, name: str, version: Optional[str] = None, variables: Optional[Dict] = None
    ) -> Optional[str]:
        target_version = version or self.default_version
        prompt_key = f"{name}_{target_version}"

        prompt_template_data = self.prompts_cache.get(prompt_key)

        if not prompt_template_data:
            logger.warning(
                f"Prompt '{prompt_key}' not found in cache. Available: {list(self.prompts_cache.keys())}"
            )
            return None

        template_str = prompt_template_data.get("template")
        if not template_str:
            logger.warning(f"No 'template' field in prompt data for '{prompt_key}'.")
            return None

        if variables:
            try:
                return template_str.format(**variables)
            except KeyError as e:
                logger.warning(f"Missing variable {e} for prompt '{prompt_key}'.")
                return template_str
        return template_str


prompt_engine = PromptEngine(
    template_dir=settings.prompts.engine.template_dir,
    default_version=settings.prompts.engine.default_version,
)
