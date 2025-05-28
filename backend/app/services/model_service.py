# backend/app/services/model_service.py
from ..config import settings, ModelConfig  # ModelConfig already imported by settings

# from ..models.base import SentimentModelInterface, LanguageModelInterface # Not directly used here
import importlib
from typing import Optional, Dict, Any
from loguru import logger


class ModelService:
    def __init__(self):
        logger.info("Initializing ModelService...")
        # Assuming settings.models.sentiment is always a ModelConfig object due to Pydantic validation
        self.sentiment_model: Optional[Any] = (
            self._load_model(  # Using Any for loaded model type
                settings.models.sentiment, "sentiment (aspect)"
            )
        )

        self.language_model: Optional[Any] = None  # Using Any for loaded model type
        if settings.models.language:  # Check if language model config exists
            logger.info(
                "Optional language model configuration found, attempting to load..."
            )
            self.language_model = self._load_model(settings.models.language, "language")
        else:
            logger.info("Language model not configured in settings, skipping load.")

        if self.sentiment_model:
            logger.success("Sentiment (aspect) model loaded successfully.")
        else:
            # _load_model already logs errors, this is a summary
            logger.error(
                "Sentiment (aspect) model FAILED to load or was not configured properly."
            )

        if self.language_model:
            logger.success("Language model loaded successfully.")
        else:
            logger.info(
                "Language model not loaded (either not configured, incomplete config, or load failed)."
            )

    def _load_model(
        self, config: Optional[ModelConfig], model_name_for_log: str
    ) -> Optional[Any]:
        method_prefix = f"ModelService._load_model (for '{model_name_for_log}')"

        if not config:
            logger.info(f"{method_prefix}: Configuration not provided. Skipping load.")
            return None

        # Ensure essential fields from ModelConfig are present
        if not config.type or not config.class_name:
            logger.warning(
                f"{method_prefix}: Configuration is incomplete (type or class_name missing). "
                f"Config: {config.model_dump(exclude_none=True)}. Skipping load."
            )
            return None

        logger.debug(
            f"{method_prefix}: Attempting to load. Type: '{config.type}', Class: '{config.class_name}'"
        )

        try:
            # Construct the module path, e.g., backend.app.models.api_models
            module_name = f"backend.app.models.{config.type}_models"
            logger.debug(f"{method_prefix}: Importing module '{module_name}'...")
            module = importlib.import_module(module_name)
            logger.debug(
                f"{method_prefix}: Module '{module_name}' imported successfully."
            )

            logger.debug(
                f"{method_prefix}: Getting class '{config.class_name}' from module '{module_name}'..."
            )
            ModelClass = getattr(module, config.class_name)
            logger.debug(
                f"{method_prefix}: Class '{config.class_name}' retrieved successfully."
            )

            # Prepare parameters for model initialization
            model_params: Dict[str, Any] = {}

            if config.type == "api":
                if not config.endpoint:  # Endpoint is crucial for API models
                    logger.error(
                        f"{method_prefix}: API model requires an 'endpoint', but it's missing in config."
                    )
                    return None
                model_params["endpoint"] = config.endpoint

                if (
                    config.api_key
                ):  # API key is optional at config level, but model might require it
                    model_params["api_key"] = config.api_key
                    logger.debug(
                        f"{method_prefix}: API key will be passed to model constructor (ending: ...{config.api_key[-4:] if len(config.api_key or '') >= 4 else 'SHORT/EMPTY'})."
                    )
                else:
                    # Model's __init__ should handle missing API key if it's mandatory for it
                    logger.info(
                        f"{method_prefix}: API key not found in config. Model will be initialized without it."
                    )

            # Add other model_type specific parameters here if you extend ModelConfig
            # Example for a local model type:
            # elif config.type == "local":
            #     if config.model_path:
            #         model_params["model_path"] = config.model_path
            #     else:
            #         logger.warning(f"{method_prefix}: Local model type specified, but 'model_path' is missing in config.")

            # If you added an 'extra_config' field to ModelConfig:
            # if config.extra_config:
            #     model_params.update(config.extra_config)

            logger.info(
                f"{method_prefix}: Initializing model class '{config.class_name}' with parameters: {model_params.keys()}"
            )  # Log keys to avoid logging sensitive values like full API key
            if "api_key" in model_params:
                logger.debug(
                    f"{method_prefix}: api_key being passed: {'Exists' if model_params['api_key'] else 'None'}"
                )

            model_instance = ModelClass(**model_params)
            logger.success(
                f"{method_prefix}: Model instance of '{config.class_name}' created successfully."
            )
            return model_instance

        except ImportError:
            logger.error(
                f"{method_prefix}: ImportError - Module '{module_name}' not found.",
                exc_info=True,
            )
        except AttributeError:
            logger.error(
                f"{method_prefix}: AttributeError - Class '{config.class_name}' not found in module '{module_name}'.",
                exc_info=True,
            )
        except (
            ValueError
        ) as ve:  # Catch specific errors like missing API key from model's __init__
            logger.error(
                f"{method_prefix}: ValueError during model initialization ('{config.class_name}'): {ve}",
                exc_info=True,
            )
        except TypeError as te:  # Catch argument mismatches for __init__
            logger.error(
                f"{method_prefix}: TypeError during model initialization ('{config.class_name}'): {te}. Check constructor arguments.",
                exc_info=True,
            )
        except Exception as e:  # Catch-all for other initialization errors
            logger.error(
                f"{method_prefix}: Unexpected exception during loading or initializing model '{config.class_name}'. "
                f"Exception type: {type(e).__name__}, Message: {e}",
                exc_info=True,
            )

        return None

    async def get_sentiment(
        self, text: str, prompt: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        method_name = "ModelService.get_sentiment"
        if not self.sentiment_model:
            logger.warning(
                f"{method_name}: Sentiment (aspect) model not loaded. Cannot predict."
            )
            return {"error": "Sentiment (aspect) model not available/loaded"}

        logger.debug(
            f"{method_name}: Predicting sentiment/aspects for text: '{text[:30]}...'"
        )

        if not hasattr(self.sentiment_model, "predict") or not callable(
            getattr(self.sentiment_model, "predict")
        ):
            logger.error(
                f"{method_name}: Loaded sentiment model object does not have a callable 'predict' method."
            )
            return {
                "error": "Sentiment model's 'predict' method is invalid or missing."
            }

        prediction_method = getattr(self.sentiment_model, "predict")

        try:
            logger.debug(
                f"{method_name}: Calling predict method of {type(self.sentiment_model).__name__}"
            )
            result: Optional[Dict[str, Any]] = await prediction_method(
                text, prompt=prompt
            )
            logger.debug(
                f"{method_name}: Raw result from model's predict method: {str(result)[:200]}..."
            )

            if result is None:
                logger.error(
                    f"{method_name}: Model's predict method returned None. This is unexpected."
                )
                return {"error": "Model prediction returned None."}

            if isinstance(result, dict) and "error" in result:
                # Safely extract parts for logging and returning
                error_message_from_model = result.get(
                    "error", "Unknown error from model"
                )
                details_from_model = result.get(
                    "details"
                )  # This will be the sub-dictionary or None
                step_from_model = result.get("step")

                # Log carefully, convert details to string for safety if it's complex
                details_str = str(details_from_model)
                if len(details_str) > 300:  # Limit length of details in log
                    details_str = details_str[:300] + "..."

                logger.error(
                    f"{method_name}: Model's predict method returned an error. "
                    f"Error Msg: '{error_message_from_model}', Step: {step_from_model}, Details Snippet: {details_str}"
                )
                # Return the structured error
                return {
                    "error": error_message_from_model,
                    "details": details_from_model,  # Pass the original details object
                    "step": step_from_model,
                }

            logger.success(
                f"{method_name}: Successfully received valid-looking result from model: {str(result)[:100]}..."
            )
            return result

        except Exception as e:
            # This is line 189 from your log
            logger.error(
                f"{method_name}: Exception occurred. Type: {type(e).__name__}, Message: '{str(e)}'",
                exc_info=True,  # CRITICAL: Ensure this gives full traceback
            )
            return {
                "error": f"Unhandled prediction error in ModelService: {type(e).__name__} - {str(e)}"
            }

    async def get_language(
        self, text: str, prompt: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        method_name = "ModelService.get_language"
        if not self.language_model:
            logger.warning(f"{method_name}: Language model not loaded. Cannot detect.")
            return {"error": "Language model not available/loaded"}

        logger.debug(f"{method_name}: Detecting language for text: '{text[:30]}...'")
        if not hasattr(self.language_model, "predict") or not callable(
            getattr(self.language_model, "predict")
        ):
            logger.error(
                f"{method_name}: Loaded language model object does not have a callable 'predict' method."
            )
            return {"error": "Language model's 'predict' method is invalid or missing."}

        prediction_method = getattr(self.language_model, "predict")

        try:
            logger.debug(
                f"{method_name}: Calling predict method of {type(self.language_model).__name__}"
            )
            result: Optional[Dict[str, Any]] = await prediction_method(
                text, prompt=prompt
            )
            logger.debug(
                f"{method_name}: Raw result from language model's predict method: {str(result)[:200]}..."
            )

            if result is None:
                logger.error(
                    f"{method_name}: Language model's predict method returned None."
                )
                return {"error": "Language model prediction returned None."}
            if isinstance(result, dict) and "error" in result:
                error_message = result.get(
                    "error", "Unknown error from language model's predict method"
                )
                details = result.get("details")
                step = result.get("step")
                logger.error(
                    f"{method_name}: Language model's predict method returned an error dictionary. "
                    f"Error: '{error_message}', Details: {details}, Step: {step}"
                )
                return {"error": error_message, "details": details, "step": step}

            logger.success(
                f"{method_name}: Successfully received valid-looking result from language model."
            )
            return result
        except Exception as e:
            logger.error(
                f"{method_name}: Exception occurred during language detection call or processing result. "
                f"Exception type: {type(e).__name__}, Message: {e}",
                exc_info=True,
            )
            return {
                "error": f"Unhandled language detection error: {type(e).__name__} - {str(e)}"
            }


model_service = ModelService()
