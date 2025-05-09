import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import Counter
import asyncio
from loguru import logger

from ..config import settings
from .model_service import model_service
from ..core import caching

from ..prompts.prompt_engine import prompt_engine


class AnalysisService:
    def __init__(self):
        logger.info("Initializing AnalysisService...")
        self.dataset_path = Path(settings.backend.dataset_path)
        self.cache_file_name = settings.backend.results_cache_file
        self.stats: Optional[Dict[str, Any]] = None
        logger.debug(
            f"Dataset path: {self.dataset_path}, Cache file name: {self.cache_file_name}"
        )

    async def _load_or_generate_stats_async(self):
        logger.debug("AnalysisService: Attempting to load or generate stats...")
        if not settings.backend.force_reanalyze_on_startup:
            self.stats = caching.load_cache(self.cache_file_name)
            if self.stats:
                logger.info("Analysis stats loaded from cache.")

        if not self.stats:
            if settings.backend.force_reanalyze_on_startup:
                logger.info("Forcing re-analysis of dataset on startup.")
            else:
                logger.info("Cache not found. Starting full analysis of dataset.")
            self.stats = await self.run_full_analysis()
        else:
            logger.debug("Stats were available, no generation needed.")

    def get_dataset_reviews(self) -> Optional[List[Dict[str, Any]]]:
        logger.debug(f"Attempting to load dataset from: {self.dataset_path}")
        if not self.dataset_path.exists():
            logger.warning(
                f"Dataset file not found: {self.dataset_path}. Creating dummy dataset."
            )
            dummy_data = {
                "review_id": [i for i in range(1, 11)],
                "product_id": [f"P10{i%5}" for i in range(10)],
                "review_text": [
                    "This is a fantastic product! Loved it.",
                    "Le produit est horrible, ne fonctionne pas.",
                    "Not bad, but could be better.",
                    "¡Excelente servicio y entrega rápida!",
                    "Ziemlich gut, aber der Kundenservice war langsam.",
                    "Happy with purchase.",
                    "Terrible quality, broke immediately.",
                    "Fantastique! Je recommande.",
                    "It's okay, nothing special.",
                    "Me encanta este producto, es genial.",
                ],
            }
            try:
                df_dummy = pd.DataFrame(dummy_data)
                self.dataset_path.parent.mkdir(parents=True, exist_ok=True)
                df_dummy.to_csv(self.dataset_path, index=False)
                logger.info(f"Created dummy dataset at: {self.dataset_path}")
            except Exception as e:
                logger.error(f"Could not create dummy dataset: {e}", exc_info=True)
                return None
        try:
            df = pd.read_csv(self.dataset_path)
            if "review_text" not in df.columns:
                logger.error("Dataset error: 'review_text' column not found.")
                return None
            logger.info(f"Dataset loaded successfully with {len(df)} reviews.")

            return df.to_dict("records")
        except Exception as e:
            logger.error(f"Error loading dataset: {e}", exc_info=True)

            return None

    async def run_full_analysis(self) -> Dict[str, Any]:
        logger.info("Starting full dataset analysis...")
        reviews = self.get_dataset_reviews()

        if not reviews:
            logger.error("Cannot run analysis, dataset could not be loaded.")

            return {"error": "Could not load reviews from dataset."}

        processed_reviews_data = []
        language_counts = Counter()
        sentiment_counts = Counter()
        sentiment_by_language = {}

        tasks = []
        for review_data in reviews:
            text = review_data.get("review_text", "")
            if text:
                tasks.append(self._process_single_review(review_data, text))
            else:
                logger.warning(
                    f"Skipping review with empty text. ID: {review_data.get('review_id', 'N/A')}"
                )

        logger.info(f"Processing {len(tasks)} reviews concurrently...")
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful_processing_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Error processing review (index {i}): {result}", exc_info=result
                )
                # Optionally store info about failed review
                continue
            if result:
                processed_reviews_data.append(result["processed_review"])
                language_counts[result["lang"]] += 1
                if result["stars"] > 0:
                    sentiment_counts[result["stars"]] += 1
                    if result["lang"] not in sentiment_by_language:
                        sentiment_by_language[result["lang"]] = Counter()
                    sentiment_by_language[result["lang"]][result["stars"]] += 1
                successful_processing_count += 1

        logger.info(
            f"Successfully processed {successful_processing_count}/{len(tasks)} reviews."
        )

        overall_stats = {
            "total_reviews_processed": successful_processing_count,
            "total_reviews_in_dataset": len(reviews),
            "language_distribution": dict(language_counts),
            "overall_sentiment_distribution": dict(sentiment_counts),
            "sentiment_distribution_by_language": {
                lang: dict(counts) for lang, counts in sentiment_by_language.items()
            },
        }

        caching.save_cache(overall_stats, self.cache_file_name)
        self.stats = overall_stats
        logger.success("Full analysis complete and stats cached.")
        return overall_stats

    async def _process_single_review(
        self, review_data: Dict, text: str
    ) -> Optional[Dict]:
        review_id = review_data.get("review_id", "N/A")
        logger.trace(f"Processing review ID: {review_id}, Text: '{text[:30]}...'")
        try:
            lang_result = await model_service.get_language(text)
            sentiment_result = await model_service.get_sentiment(text)

            lang = lang_result.get("language", "unknown") if lang_result else "unknown"
            stars = sentiment_result.get("stars", 0) if sentiment_result else 0

            processed_review = {
                "review_id": review_id,
                "text_preview": text[:50] + "...",
                "detected_language": lang,
                "predicted_sentiment_stars": stars,
            }
            logger.trace(
                f"Review ID {review_id} processed. Lang: {lang}, Stars: {stars}"
            )
            return {"processed_review": processed_review, "lang": lang, "stars": stars}
        except Exception as e:
            logger.error(
                f"Exception while processing single review ID {review_id}: {e}",
                exc_info=True,
            )
            # This exception will be caught by asyncio.gather if return_exceptions=True
            raise  # Or return None / error structure

    def get_stats(self) -> Optional[Dict[str, Any]]:
        if not self.stats:
            logger.warning("Stats requested but not yet available/generated.")
            return {
                "status": "loading",
                "message": "Statistics are being generated or loaded. Please try again shortly.",
            }
        logger.debug("Stats retrieved from AnalysisService instance.")
        return self.stats


_analysis_service_instance: Optional[AnalysisService] = None


async def initialize_analysis_service():
    global _analysis_service_instance
    logger.debug("Attempting to initialize AnalysisService...")
    if _analysis_service_instance is None:
        logger.info("AnalysisService instance not found, creating new one.")
        _analysis_service_instance = AnalysisService()
        await _analysis_service_instance._load_or_generate_stats_async()
        logger.success("AnalysisService initialized and stats loaded/generated.")
    else:
        logger.debug("AnalysisService instance already exists.")
    return _analysis_service_instance


def get_analysis_service() -> AnalysisService:
    if _analysis_service_instance is None:
        logger.critical("AnalysisService accessed before async initialization!")
        raise RuntimeError(
            "AnalysisService not initialized. Ensure initialize_analysis_service() is awaited at application startup."
        )
    return _analysis_service_instance
