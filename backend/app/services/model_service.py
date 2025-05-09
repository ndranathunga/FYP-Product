from ..config import settings
from ..models.base import SentimentModelInterface, LanguageModelInterface
import importlib
from typing import Optional, Dict, Any
from loguru import logger  


class ModelService:
    def __init__(self):
        logger.info("Initializing ModelService...")
        self.sentiment_model: Optional[SentimentModelInterface] = self._load_model(
            settings.models.sentiment, "sentiment"
        )
        self.language_model: Optional[LanguageModelInterface] = self._load_model(
            settings.models.language, "language"
        )
        if self.sentiment_model:
            logger.success("Sentiment model loaded successfully.")
        else:
            logger.error("Sentiment model FAILED to load.")
        if self.language_model:
            logger.success("Language model loaded successfully.")
        else:
            logger.error("Language model FAILED to load.")

    def _load_model(self, config, model_name_for_log: str):
        logger.debug(
            f"Attempting to load {model_name_for_log} model. Config: {config.model_dump()}"
        )
        model_type = config.type
        class_name = config.class_name

        if not class_name:
            logger.error(
                f"'class' (class_name) not specified for {model_name_for_log} model in settings.yaml."
            )
            return None

        try:
            module_name = f"backend.app.models.{model_type}_models"
            module = importlib.import_module(module_name)
            ModelClass = getattr(module, class_name)
            logger.debug(
                f"Found class {class_name} in module {module_name} for {model_name_for_log} model."
            )

            model_params = {}
            if model_type == "api":
                if not config.endpoint:
                    logger.error(
                        f"API endpoint not configured for {model_name_for_log} model (type: api)."
                    )
                    return None
                model_params["endpoint"] = config.endpoint
                if config.api_key:
                    model_params["api_key"] = config.api_key

            logger.info(
                f"Initializing {model_name_for_log} model ({class_name}) with params: {model_params}"
            )
            return ModelClass(**model_params)
        except ImportError:
            logger.error(
                f"Module {module_name} not found for {model_name_for_log} model.",
                exc_info=True,
            )
        except AttributeError:
            logger.error(
                f"Class {class_name} not found in module {module_name} for {model_name_for_log} model.",
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                f"Error loading {model_name_for_log} model ({class_name}): {e}",
                exc_info=True,
            )
        return None

    async def get_sentiment(
        self, text: str, prompt: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if not self.sentiment_model:
            logger.warning("Sentiment model not loaded, cannot predict sentiment.")
            return {"error": "Sentiment model not loaded"}

        logger.debug(f"Predicting sentiment for text: '{text[:30]}...'")
        prediction_method = getattr(self.sentiment_model, "predict", None)
        if not callable(prediction_method):
            logger.error("Sentiment model 'predict' method not found or not callable.")
            return {
                "error": "Sentiment model 'predict' method not found or not callable."
            }

        try:
            if (
                settings.models.sentiment.type == "api"
            ):  # Check if it's an API model for potential async call
                return await prediction_method(text, prompt=prompt)  # type: ignore
            else:
                return prediction_method(text, prompt=prompt)  # type: ignore
        except Exception as e:
            logger.error(f"Error during sentiment prediction: {e}", exc_info=True)
            return {"error": f"Prediction error: {str(e)}"}

    async def get_language(
        self, text: str, prompt: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if not self.language_model:
            logger.warning("Language model not loaded, cannot detect language.")
            return {"error": "Language model not loaded"}

        logger.debug(f"Detecting language for text: '{text[:30]}...'")
        prediction_method = getattr(self.language_model, "predict", None)
        if not callable(prediction_method):
            logger.error("Language model 'predict' method not found or not callable.")
            return {
                "error": "Language model 'predict' method not found or not callable."
            }

        try:
            if settings.models.language.type == "api":  # Check if it's an API model
                return await prediction_method(text, prompt=prompt)  # type: ignore
            else:
                return prediction_method(text, prompt=prompt)  # type: ignore
        except Exception as e:
            logger.error(f"Error during language detection: {e}", exc_info=True)
            return {"error": f"Prediction error: {str(e)}"}


model_service = ModelService()
