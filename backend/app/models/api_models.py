# backend/app/models/api_models.py
import ast
from .base import SentimentModelInterface, LanguageModelInterface
from typing import Dict, Any, Optional
import httpx
import random  # For APISentimentModel stub
import json  # FOR json.loads()
import time
import re

# import os # Not currently used in this file
# import ast # NO LONGER NEEDED if using json.loads()
import asyncio
from loguru import logger
import traceback  # For manual traceback printing if needed


def fix_jsonish(raw: Optional[str]) -> Optional[str]:
    if not isinstance(raw, str):
        return raw

    # 1. Convert Python booleans/null to JSON
    s = raw.replace("True", "true").replace("False", "false").replace("None", "null")
    
    # 2. Convert single-quoted keys to double-quoted keys
    # This regex is reasonably safe for keys like 'key_name':
    s = re.sub(r"(?P<prefix>[\{\s,])'(?P<key>[A-Za-z_][A-Za-z0-9_]*)'\s*:", 
               lambda m: f"{m.group('prefix')}\"{m.group('key')}\":", s)

    # 3. Convert single-quoted string VALUES to double-quoted string VALUES.
    # THIS IS THE HARDEST PART. The previous attempt was problematic.
    # A robust solution for this step with regex is very difficult if values can contain quotes.
    # For "it's", after key conversion, we might have: "justification": 'it's terrible'
    # We want: "justification": "it's terrible" (json.loads handles ' inside ")
    # A global replace("'", "\"") at this stage would break "it's" -> "it"s"

    # If we assume keys are now double-quoted, and we only want to change
    # single quotes that delimit entire string values:
    # Example: "key": 'value' -> "key": "value"
    # Example: "key": 'it's value' -> "key": "it's value" (this is what we want for json.loads)

    # This regex attempts to find ': '...' and replace the outer quotes.
    # It tries to capture content, allowing escaped single quotes inside.
    # (?<!\\) means "not preceded by a backslash".
    def replace_value_quotes(match):
        # val_content already has its internal single quotes.
        # We just need to wrap it in double quotes for JSON.
        val_content = match.group(1)
        # We don't need to escape single quotes within val_content for JSON if val_content is wrapped in double quotes.
        return f': "{val_content}"'

    # This regex is still imperfect for complex nested strings or already escaped content.
    # It looks for ': '...' and makes it ': "..."'
    # It tries to capture content between single quotes, allowing escaped single quotes inside.
    # Pattern: : \s* ' ( (?: \\. | [^'\\] )* ) '
    #            ^   ^ ^         ^------------^   ^
    #            |   | |         | content      | closing '
    #            |   | opening ' | (escaped char OR not ' or \) zero or more times
    #            |   optional whitespace
    #            colon
    s = re.sub(r":\s*'((?:\\.|[^'\\])*)'", replace_value_quotes, s)
    
    # Also handle single-quoted strings in lists: ['item'] -> ["item"]
    s = re.sub(r"(?<=[\[,]\s*)'((?:\\.|[^'\\])*)'(?=\s*[,\]])", r'"\1"', s)

    return s


class APISentimentModel(SentimentModelInterface):  # Your existing stub
    def __init__(self, endpoint: str, api_key: Optional[str] = None, **kwargs):
        self.endpoint = endpoint
        self.api_key = api_key
        self.client = httpx.AsyncClient()
        logger.info(
            f"Initializing APISentimentModel (stub) for endpoint: {self.endpoint}, Config: {kwargs}"
        )

    async def predict(self, text: str, prompt: Optional[str] = None) -> Dict[str, Any]:
        logger.info(
            f"APISentimentModel predicting for: {text[:30]}... (would call {self.endpoint})"
        )
        if prompt:
            logger.info(f"Using prompt: {prompt}")
        return {
            "stars": random.randint(1, 5),
            "confidence": round(random.uniform(0.6, 0.95), 2),
            "source": "api_dummy",
            "model_type": "api_stub",
        }


class RunPodAspectModel(SentimentModelInterface):
    def __init__(self, endpoint: str, api_key: Optional[str] = None, **kwargs):
        self.base_endpoint = endpoint.rstrip("/")
        self.api_key = api_key

        if not self.api_key:
            logger.critical(
                "RunPod API Key not provided for RunPodAspectModel. This is required."
            )
            raise ValueError("RunPod API Key is required for RunPodAspectModel.")
        if not self.base_endpoint:
            logger.critical(
                "RunPod endpoint not configured for RunPodAspectModel. This is required."
            )
            raise ValueError("RunPod endpoint is required for RunPodAspectModel.")

        self.client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=300.0))
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        logger.info(
            f"RunPodAspectModel Initialized. Endpoint: {self.base_endpoint}, API Key ending: ...{self.api_key[-4:] if self.api_key and len(self.api_key) >=4 else 'KEY_INVALID_OR_SHORT'}"
        )

    async def predict(self, text: str, prompt: Optional[str] = None) -> Dict[str, Any]:
        method_name = "RunPodAspectModel.predict"
        logger.debug(
            f"{method_name}: Predicting for text (first 50 chars): '{text[:50]}...'"
        )
        if prompt:
            logger.warning(
                f"{method_name}: Received 'prompt' argument, but it's ignored by this model."
            )

        run_url = f"{self.base_endpoint}/run"
        payload = {"input": {"review": text}}

        try:
            logger.debug(f"{method_name}: Sending POST to RunPod /run: {run_url}")
            logger.trace(f"{method_name}: RunPod /run payload: {payload}")

            response = await self.client.post(
                run_url, headers=self.headers, json=payload
            )

            logger.debug(
                f"{method_name}: Initial /run response status: {response.status_code}"
            )
            if response.status_code >= 300:
                logger.warning(
                    f"{method_name}: Initial /run call received non-2xx status {response.status_code}. Response body: {response.text[:500]}"
                )
            response.raise_for_status()

            initial_data = response.json()
            logger.debug(
                f"{method_name}: RunPod /run initial successful response JSON: {initial_data}"
            )

            job_id = initial_data.get("id")
            if not job_id:
                error_msg = (
                    "Failed to submit job to RunPod, no job ID in /run response."
                )
                logger.error(
                    f"{method_name}: {error_msg} Full /run response: {initial_data}"
                )
                return {
                    "error": error_msg,
                    "details": initial_data,
                    "step": "get_job_id",
                }

            status_url = f"{self.base_endpoint}/status/{job_id}"
            logger.info(
                f"{method_name}: Job submitted. ID: {job_id}. Polling status at: {status_url}"
            )

            max_wait_time_seconds = 300
            initial_poll_interval_seconds = 5
            max_poll_interval_seconds = 30
            poll_interval_seconds = initial_poll_interval_seconds
            start_time = time.time()

            while True:
                current_time = time.time()
                if current_time - start_time > max_wait_time_seconds:
                    error_msg = f"Job {job_id} timed out after {max_wait_time_seconds}s polling."
                    logger.error(f"{method_name}: {error_msg}")
                    return {
                        "error": error_msg,
                        "job_id": job_id,
                        "step": "polling_timeout",
                    }

                await asyncio.sleep(poll_interval_seconds)
                logger.debug(
                    f"{method_name}: Polling job {job_id} (interval: {poll_interval_seconds}s)"
                )

                status_response = await self.client.get(
                    status_url, headers=self.headers
                )
                logger.debug(
                    f"{method_name}: Polling response status for job {job_id}: {status_response.status_code}"
                )

                if status_response.status_code == 429:
                    logger.warning(
                        f"{method_name}: Job {job_id} poll got 429 Too Many Requests. Increasing interval."
                    )
                    poll_interval_seconds = min(
                        poll_interval_seconds * 2, max_poll_interval_seconds
                    )
                    continue

                if status_response.status_code >= 300:
                    logger.warning(
                        f"{method_name}: Polling job {job_id} received non-2xx status {status_response.status_code}. Response body: {status_response.text[:500]}"
                    )
                status_response.raise_for_status()

                status_data = status_response.json()
                logger.trace(
                    f"{method_name}: Job {job_id} status data (full): {status_data}"
                )
                current_status = status_data.get("status")

                if current_status == "COMPLETED":
                    logger.success(
                        f"{method_name}: Job {job_id} COMPLETED. Preparing to process output."
                    )
                    logger.debug(
                        f"{method_name}: Full status_data for COMPLETED job {job_id}: {status_data}"
                    )

                    output_from_status = status_data.get("output", {})
                    logger.debug(
                        f"{method_name}: Extracted 'output' field (type: {type(output_from_status).__name__}): {str(output_from_status)[:200]}..."
                    )
                    if not isinstance(output_from_status, dict):
                        error_msg = f"Job {job_id} COMPLETED, but 'output' field is not a dictionary as expected."
                        logger.error(
                            f"{method_name}: {error_msg} Received 'output' type: {type(output_from_status).__name__}, value: {str(output_from_status)[:200]}"
                        )
                        return {
                            "error": error_msg,
                            "details": {"output_received": output_from_status},
                            "job_id": job_id,
                            "step": "completed_output_not_dict",
                        }

                    result_from_output = output_from_status.get("result", {})
                    logger.debug(
                        f"{method_name}: Extracted 'result' field from 'output' (type: {type(result_from_output).__name__}): {str(result_from_output)[:200]}..."
                    )
                    if not isinstance(result_from_output, dict):
                        error_msg = f"Job {job_id} COMPLETED, but 'output.result' field is not a dictionary as expected."
                        logger.error(
                            f"{method_name}: {error_msg} Received 'result' type: {type(result_from_output).__name__}, value: {str(result_from_output)[:200]}"
                        )
                        return {
                            "error": error_msg,
                            "details": {"result_received": result_from_output},
                            "job_id": job_id,
                            "step": "completed_result_not_dict",
                        }

                    raw_output_str = result_from_output.get("raw")
                    logger.debug(
                        f"{method_name}: Extracted 'raw' field from 'output.result' (type: {type(raw_output_str).__name__}): '{str(raw_output_str)[:100]}...' for job {job_id}"
                    )

                    if raw_output_str and isinstance(raw_output_str, str):
                        parsed_output = None
                        logger.info(
                            f"{method_name}: [JSON_LOAD_BLOCK_ENTER] Job {job_id}. Attempting json.loads. Raw string snippet: '{raw_output_str[:100]}...'"
                        )
                        try:
                            # SWITCHED TO json.loads()
                            # temp = fix_jsonish(raw_output_str)
                            temp = re.sub(r"(?<=[a-zA-Z])'(?!')(?=[a-zA-Z])", "", raw_output_str)
                            temp = temp.replace("'", "\"")
                            logger.debug(
                                f"{method_name}: Fixed JSON string for job {job_id}: Fixed JSON: '{temp}'"
                            )
                            parsed_output = json.loads(temp)
                            logger.info(
                                f"{method_name}: [JSON_LOAD_BLOCK_SUCCESS] Job {job_id}. json.loads successful. Type: {type(parsed_output).__name__}"
                            )

                        except json.JSONDecodeError as e_json_decode:
                            error_msg_for_client = f"json.loads FAILED for job {job_id} with {type(e_json_decode).__name__}: {e_json_decode}."
                            logger.error(
                                "{method}: [JSON_LOAD_BLOCK_FAIL] {error_msg}. Problematic Raw string (repr): {raw_repr}",
                                method=method_name,
                                error_msg=error_msg_for_client,
                                raw_repr=repr(raw_output_str),
                                exc_info=True,
                            )
                            return {
                                "error": error_msg_for_client,
                                "details": f"Original exception: {str(e_json_decode)}. Check logs for raw string repr.",
                                "job_id": job_id,
                                "step": "json_decode_error",
                            }

                        logger.info(
                            f"{method_name}: [JSON_LOAD_BLOCK_EXIT] Job {job_id}. parsed_output is type: {type(parsed_output).__name__ if parsed_output is not None else 'NoneType'}"
                        )

                        if parsed_output is not None:
                            if not isinstance(parsed_output, dict):
                                error_msg = "Parsed 'raw' output (from json.loads) is not a dictionary."
                                logger.error(
                                    f"{method_name} for job {job_id}: {error_msg} Parsed type: {type(parsed_output).__name__}"
                                )
                                return {
                                    "error": error_msg,
                                    "job_id": job_id,
                                    "step": "parsed_json_not_dict",
                                }

                            logger.debug(
                                f"{method_name}: Checking for 'aspects' key in parsed_output (keys: {list(parsed_output.keys())}) for job {job_id}."
                            )
                            if "aspects" not in parsed_output:
                                error_msg = "Parsed 'raw' output dictionary (from json.loads) is missing 'aspects' key."
                                logger.error(
                                    f"{method_name} for job {job_id}: {error_msg} Parsed dict keys: {list(parsed_output.keys())}"
                                )
                                return {
                                    "error": error_msg,
                                    "job_id": job_id,
                                    "step": "missing_aspects_key_from_json",
                                }

                            logger.debug(
                                f"{method_name}: Job {job_id} successfully processed. Returning parsed_output."
                            )
                            return parsed_output  # SUCCESSFUL RETURN
                        else:
                            logger.error(
                                f"{method_name}: Job {job_id}. parsed_output is None after json.loads block without exception. This is unexpected. Raw string was: '{raw_output_str[:200]}...'"
                            )
                            return {
                                "error": "Internal error: parsed_output is None after successful-looking json.loads",
                                "job_id": job_id,
                                "step": "internal_parsed_output_none_post_json_load",
                            }
                    else:
                        error_msg = "'raw' output string missing, not a string, or empty in COMPLETED job."
                        logger.warning(
                            f"{method_name} for job {job_id}: {error_msg} Type: {type(raw_output_str).__name__ if raw_output_str is not None else 'NoneType'}."
                        )
                        return {
                            "error": error_msg,
                            "details": {"output_result": result_from_output},
                            "job_id": job_id,
                            "step": "missing_or_invalid_raw_output_str_for_json",
                        }

                elif current_status in ["IN_QUEUE", "IN_PROGRESS", "UPLOADING_OUTPUT"]:
                    delay_time_ms = status_data.get("delayTime", 0)
                    execution_time_ms = status_data.get("executionTime", 0)
                    logger.info(
                        f"{method_name}: Job {job_id} status: {current_status}. Delay: {delay_time_ms/1000.0:.2f}s. Exec: {execution_time_ms/1000.0:.2f}s."
                    )
                    if delay_time_ms > 60000 and poll_interval_seconds < 20:
                        poll_interval_seconds = 20
                    elif delay_time_ms > 20000 and poll_interval_seconds < 10:
                        poll_interval_seconds = 10
                    elif (
                        current_status == "IN_PROGRESS"
                        and poll_interval_seconds > initial_poll_interval_seconds
                    ):
                        poll_interval_seconds = initial_poll_interval_seconds

                elif current_status == "FAILED":
                    error_msg = f"RunPod job {job_id} status is FAILED."
                    logger.error(
                        f"{method_name}: {error_msg} RunPod Data: {status_data}"
                    )
                    return {
                        "error": error_msg,
                        "details": status_data,
                        "job_id": job_id,
                        "step": "job_failed_status_reported_by_runpod",
                    }
                else:
                    logger.warning(
                        f"{method_name}: Job {job_id} has unknown status: '{current_status}'. Data: {status_data}"
                    )

        except httpx.HTTPStatusError as e_http:
            error_body = e_http.response.text[:500]
            error_details_parsed = {"raw_body": error_body}
            try:
                error_details_parsed.update(e_http.response.json())
            except json.JSONDecodeError:
                pass
            error_msg = f"HTTP error {e_http.response.status_code} from RunPod API: {e_http.request.method} {e_http.request.url}"
            logger.error(
                f"{method_name}: {error_msg}. Response details: {error_details_parsed}",
                exc_info=False,
            )
            return {
                "error": error_msg,
                "status_code": e_http.response.status_code,
                "details": error_details_parsed,
                "step": "http_status_error_main_try",
            }

        except httpx.RequestError as e_req:
            error_msg = f"Request error calling RunPod API ({e_req.request.method} {e_req.request.url}): {type(e_req).__name__} - {str(e_req)}"
            logger.error(f"{method_name}: {error_msg}", exc_info=True)
            return {
                "error": error_msg,
                "exception_type": type(e_req).__name__,
                "step": "request_error_main_try",
            }

        except Exception as e_unexpected:
            error_msg_for_client = f"Outer try-block unexpected error in {method_name}: {type(e_unexpected).__name__} - {str(e_unexpected)}"
            logger.critical(
                "{method} CRITICAL UNEXPECTED ERROR (outer try-block): Type={err_type}, Msg='{err_msg}', Repr={err_repr}",
                method=method_name,
                err_type=type(e_unexpected).__name__,
                err_msg=str(e_unexpected),
                err_repr=repr(e_unexpected),
                exc_info=True,
            )
            return {
                "error": error_msg_for_client,
                "exception_type": type(e_unexpected).__name__,
                "step": "unexpected_exception_in_predict_outer_try_block",
            }

        logger.error(
            f"{method_name}: Predict method is exiting without a proper return from the main loop. Last status was '{current_status if 'current_status' in locals() else 'unknown'}'."
        )
        return {
            "error": "Predict method exited loop unexpectedly",
            "job_id": job_id if "job_id" in locals() else None,
            "step": "unexpected_loop_exit_fallback",
        }


class APILanguageModel(LanguageModelInterface):
    def __init__(self, endpoint: str, api_key: Optional[str] = None, **kwargs):
        self.endpoint = endpoint
        self.api_key = api_key
        self.client = httpx.AsyncClient()
        logger.info(
            f"Initializing APILanguageModel (stub) for endpoint: {self.endpoint}, Config: {kwargs}"
        )

    async def predict(self, text: str, prompt: Optional[str] = None) -> Dict[str, Any]:
        logger.info(
            f"APILanguageModel predicting for: {text[:30]}... (would call {self.endpoint})"
        )
        if prompt:
            logger.info(f"Using prompt: {prompt}")
        return {
            "language": "en_api_dummy",
            "confidence": round(random.uniform(0.7, 0.98), 2),
            "source": "api_dummy",
            "model_type": "api_stub",
        }
