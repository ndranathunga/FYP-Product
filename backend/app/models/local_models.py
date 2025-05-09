from .base import SentimentModelInterface, LanguageModelInterface
from typing import Dict, Any, Optional
import random
from loguru import logger


class LocalSentimentModel(SentimentModelInterface):
    def __init__(self, model_path: Optional[str] = None, **kwargs):
        logger.info(
            f"Initializing LocalSentimentModel (stub). Path: {model_path}, Config: {kwargs}"
        )

    def predict(self, text: str, prompt: Optional[str] = None) -> Dict[str, Any]:
        logger.debug(f"LocalSentimentModel predicting for: {text[:30]}...")
        if prompt:
            logger.debug(f"Using prompt: {prompt}")
        return {
            "stars": random.randint(1, 5),
            "confidence": round(random.uniform(0.7, 0.99), 2),
            "model_type": "local_stub",
        }


class LocalLanguageModel(LanguageModelInterface):
    def __init__(self, model_path: Optional[str] = None, **kwargs):
        logger.info(
            f"Initializing LocalLanguageModel (stub). Path: {model_path}, Config: {kwargs}"
        )

    def predict(self, text: str, prompt: Optional[str] = None) -> Dict[str, Any]:
        logger.debug(f"LocalLanguageModel predicting for: {text[:30]}...")
        if prompt:
            logger.debug(f"Using prompt: {prompt}")
        if any(char in "éàçê" for char in text.lower()):
            lang = "fr"
        elif any(char in "ñáéíóúü" for char in text.lower()):
            lang = "es"
        elif any(char in "äöüß" for char in text.lower()):
            lang = "de"
        else:
            lang = "en"
        return {
            "language": lang,
            "confidence": round(random.uniform(0.8, 0.99), 2),
            "model_type": "local_stub",
        }
