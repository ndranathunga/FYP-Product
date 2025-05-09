from dash import html, dcc, callback, Input, Output, State  
import dash_bootstrap_components as dbc
import httpx
import json
import sys
from pathlib import Path
from loguru import logger  

DASH_TESTING_DIR = Path(__file__).resolve().parent
DASH_APP_DIR_T = DASH_TESTING_DIR.parent
FRONTEND_DIR_T = DASH_APP_DIR_T.parent
PROJECT_ROOT_FOR_DASH_TESTING = FRONTEND_DIR_T.parent

if str(PROJECT_ROOT_FOR_DASH_TESTING) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_DASH_TESTING))

try:
    from backend.app.config import settings as backend_settings_testing

    API_BASE_URL = f"http://{backend_settings_testing.backend.host}:{backend_settings_testing.backend.port}/api/v1"
    logger.trace(
        f"Testing Page: API_BASE_URL set to {API_BASE_URL} from backend settings."
    )
except ImportError as e:
    API_BASE_URL = "http://127.0.0.1:8000/api/v1"  # Fallback
    logger.warning(
        f"Testing Page: Could not import backend_settings. Defaulting API_BASE_URL to {API_BASE_URL}. Error: {e}"
    )


layout = dbc.Container(
    [
        dbc.Row(dbc.Col(html.H3("Test Models"), width=12, className="mb-3 mt-3")),
        dbc.Row(
            dbc.Col(
                [
                    dbc.Label(
                        "Enter Review Text:", html_for="review-input-text-testing"
                    ),
                    dcc.Textarea(
                        id="review-input-text-testing",
                        placeholder="Enter customer review here...",
                        style={"width": "100%", "height": 100},
                        className="mb-2 form-control",
                    ),
                    dbc.Button(
                        "Analyze Review",
                        id="analyze-button-testing",
                        color="success",
                        n_clicks=0,
                        className="mt-2",
                    ),  # n_clicks added for callback
                ],
                md=12,
            ),
            className="mb-4",
        ),
        dbc.Row(
            dbc.Col(
                dcc.Loading(
                    html.Div(id="analysis-output-display-testing", className="mt-3")
                ),
                md=12,
            )
        ),
    ],
    fluid=True,
)


@callback(
    Output("analysis-output-display-testing", "children"),
    Input("analyze-button-testing", "n_clicks"),
    State("review-input-text-testing", "value"),
    prevent_initial_call=True,
)
def handle_analyze_review_testing(n_clicks, review_text):
    logger.debug(
        f"Analyze review button clicked (n_clicks: {n_clicks}). Review text length: {len(review_text) if review_text else 0}"
    )
    if not review_text or not review_text.strip():
        logger.info("Analyze review: No review text entered.")
        return dbc.Alert("Please enter some review text to analyze.", color="warning")

    try:
        payload = {"text": review_text}
        logger.trace(
            f"Sending POST request to {API_BASE_URL}/analyze_review with payload: {payload}"
        )
        response = httpx.post(
            f"{API_BASE_URL}/analyze_review", json=payload, timeout=15.0
        )
        logger.trace(
            f"API response status code: {response.status_code} for /analyze_review"
        )
        response.raise_for_status()

        results = response.json()
        logger.success(f"Successfully received analysis results: {results}")

        lang_info = results.get("language", {}) or {}
        sent_info = results.get("sentiment", {}) or {}

        # Defensive formatting for confidence values
        lang_conf_str = (
            f"{lang_info.get('confidence', 'N/A'):.2f}"
            if isinstance(lang_info.get("confidence"), (int, float))
            else "N/A"
        )
        sent_conf_str = (
            f"{sent_info.get('confidence', 'N/A'):.2f}"
            if isinstance(sent_info.get("confidence"), (int, float))
            else "N/A"
        )

        return dbc.Card(
            [
                dbc.CardHeader(html.H4("Analysis Results", className="m-0")),
                dbc.CardBody(
                    [
                        html.H5("Language Detection:", className="card-title"),
                        html.P(
                            [
                                html.Strong("Language: "),
                                f"{lang_info.get('language', 'N/A').upper()}",
                                html.Br(),
                                html.Strong("Confidence: "),
                                lang_conf_str,
                                html.Br(),
                                html.Strong("Model Type: "),
                                f"{lang_info.get('model_type', 'N/A')}",
                            ],
                            className="card-text",
                        ),
                        html.Hr(),
                        html.H5("Sentiment Analysis:", className="card-title"),
                        html.P(
                            [
                                html.Strong("Predicted Stars: "),
                                f"{sent_info.get('stars', 'N/A')} ⭐",
                                html.Br(),
                                html.Strong("Confidence: "),
                                sent_conf_str,
                                html.Br(),
                                html.Strong("Model Type: "),
                                f"{sent_info.get('model_type', 'N/A')}",
                            ],
                            className="card-text",
                        ),
                        html.Hr(),
                        html.H6("Raw JSON Output:", className="mt-3"),
                        html.Pre(
                            json.dumps(results, indent=2),
                            style={
                                "backgroundColor": "#f8f9fa",
                                "border": "1px solid #dee2e6",
                                "padding": "10px",
                                "maxHeight": "300px",
                                "overflowY": "auto",
                            },
                        ),
                    ]
                ),
            ]
        )

    except httpx.RequestError as e:
        logger.error(f"API Connection Error during review analysis: {e}", exc_info=True)
        return dbc.Alert(
            f"Could not connect to the analysis API: {e}",
            color="danger",
            className="mt-3",
        )
    except httpx.HTTPStatusError as e:
        error_detail = e.response.text
        try:
            error_json = e.response.json()
            error_detail = error_json.get("detail", error_detail)
        except json.JSONDecodeError:  # If response is not JSON
            logger.debug(
                f"API error response for status {e.response.status_code} was not valid JSON."
            )
            pass
        logger.error(
            f"API HTTP Status Error {e.response.status_code} during review analysis: {error_detail}",
            exc_info=True,
        )
        return dbc.Alert(
            f"API Error ({e.response.status_code}): {error_detail}",
            color="danger",
            className="mt-3",
        )
    except Exception as e:
        logger.critical(
            f"Unexpected error during review analysis: {str(e)}", exc_info=True
        )
        return dbc.Alert(
            f"An unexpected error occurred: {str(e)}", color="danger", className="mt-3"
        )
