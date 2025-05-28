# frontend/dashboard/pages/testing.py
from dash import html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
import httpx
import json
from loguru import logger
from pathlib import Path
import sys

# --- Path Setup & API Base URL (from your existing code) ---
DASH_TESTING_DIR = Path(__file__).resolve().parent
DASH_APP_DIR_T = DASH_TESTING_DIR.parent
FRONTEND_DIR_T = DASH_APP_DIR_T.parent
PROJECT_ROOT_FOR_DASH_TESTING = FRONTEND_DIR_T.parent

if str(PROJECT_ROOT_FOR_DASH_TESTING) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_DASH_TESTING))

try:
    from backend.app.config import settings as backend_settings_testing

    api_host = backend_settings_testing.backend.host
    if api_host == "0.0.0.0":
        api_host = "127.0.0.1"
    API_BASE_URL = f"http://{api_host}:{backend_settings_testing.backend.port}/api/v1"
    logger.trace(
        f"Testing Page: API_BASE_URL set to {API_BASE_URL} from backend settings."
    )
except ImportError:
    API_BASE_URL = "http://127.0.0.1:8000/api/v1"
    logger.warning(
        f"Testing Page: Could not import backend_settings. Defaulting API_BASE_URL to {API_BASE_URL}"
    )
# --- End Path Setup ---

layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H3("Test Aspect Analysis Model"),
                width=12,
                className="mb-3 mt-3",
            )
        ),
        dbc.Row(
            dbc.Col(
                [
                    dbc.Label("Enter Review Text:", html_for="testing-review-input"),
                    dcc.Textarea(
                        id="testing-review-input",
                        placeholder="Enter customer review here...",
                        style={"width": "100%", "height": 120},
                        className="mb-2 form-control",
                    ),
                    dbc.Label(
                        "Optional Product ID (for context):",
                        html_for="testing-product-id-context",
                        className="mt-2",
                    ),
                    dcc.Input(
                        id="testing-product-id-context",
                        type="text",
                        placeholder="e.g., P123 (optional context)",
                        className="form-control mb-2",
                    ),
                    dbc.Button(
                        "Analyze Review Aspects",
                        id="testing-analyze-button",
                        color="success",
                        className="mt-2",
                    ),
                ],
                md=12,
            ),
            className="mb-4",
        ),
        dbc.Row(
            dbc.Col(
                dcc.Loading(
                    html.Div(id="testing-analysis-output-display", className="mt-3")
                ),
                md=12,
            )
        ),
    ],
    fluid=True,
)


def format_aspect_test_results(analysis_data: dict):
    if not analysis_data or analysis_data.get("error"):
        error_message = (
            analysis_data.get("error", "Unknown error occurred.")
            if analysis_data
            else "No analysis data."
        )
        return dbc.Alert(f"Error: {error_message}", color="danger", className="mt-3")

    aspects = analysis_data.get("aspects_data", [])
    if not aspects:
        return dbc.Alert(
            "No aspects were identified in the review by the model.",
            color="info",
            className="mt-3",
        )

    aspect_cards_content = []
    for aspect in aspects:
        name = aspect.get("name", "N/A Aspect")
        rating = aspect.get("rating", "N/A")
        justification = aspect.get("justification", "No justification provided.")
        if rating == 0:
            continue
            # rating = "N/A (Not Mentioned)"

        if justification == "Not mentioned in the review.":
            continue

        card_color = "light"
        if isinstance(rating, (int, float)) and rating > 0:
            if rating >= 4:
                card_color = "success"
            elif rating == 3:
                card_color = "warning"
            else:
                card_color = "danger"

        header_class = (
            f"text-white bg-{card_color}"
            if card_color not in ["light", "secondary"]
            else ""
        )

        aspect_cards_content.append(
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader(f"Aspect: {name}", className=header_class),
                        dbc.CardBody(
                            [
                                html.H5(
                                    f"Rating: {rating} {'★' if isinstance(rating, (int,float)) and rating > 0 else ''}",
                                    className="card-title",
                                ),
                                html.P(
                                    f"Justification: {justification}",
                                    className="card-text",
                                ),
                            ]
                        ),
                    ],
                    color=card_color,
                    outline=(card_color in ["light", "secondary"]),
                    className="mb-3 h-100",
                ),
                md=4,
                xs=12,
            )
        )

    raw_output_display = html.Details(
        [
            html.Summary("Raw Model JSON Output"),
            html.Pre(
                json.dumps(analysis_data.get("raw_model_output", {}), indent=2),
                style={
                    "backgroundColor": "#f8f9fa",
                    "border": "1px solid #dee2e6",
                    "padding": "10px",
                    "maxHeight": "250px",
                    "overflowY": "auto",
                    "fontSize": "0.85em",
                },
            ),
        ],
        className="mt-3",
    )

    return html.Div(
        [
            html.H4(
                f"Aspect Analysis Results",
                className="mt-4 mb-3",
            ),
            dbc.Row(aspect_cards_content),
            raw_output_display,
        ]
    )


@callback(
    Output("testing-analysis-output-display", "children"),
    Input("testing-analyze-button", "n_clicks"),
    [
        State("testing-review-input", "value"),
        State("testing-product-id-context", "value"),
        State("jwt-token-store", "data"),
    ],
    prevent_initial_call=True,
)
def handle_analyze_review_testing_page(
    n_clicks, review_text, product_id_context, jwt_token
):
    if not review_text or not review_text.strip():
        return dbc.Alert("Please enter some review text to analyze.", color="warning")
    if not jwt_token:
        return dbc.Alert("Authentication required to test models.", color="danger")

    headers = {"Authorization": f"Bearer {jwt_token}"}
    # Use the AdhocReviewInput schema for the API
    payload = {
        "text": review_text,
        "product_id_context": (
            product_id_context
            if product_id_context and product_id_context.strip()
            else "ad_hoc_test_page"
        ),
    }
    api_url = f"{API_BASE_URL}/analyze_adhoc_review"  # Endpoint from analysis_stats.py

    try:
        logger.info(f"TestingPage: Sending ad-hoc analysis request to {api_url}")
        response = httpx.post(
            api_url, json=payload, headers=headers, timeout=310.0
        )  # Increased for RunPod cold starts
        response.raise_for_status()

        results_data = (
            response.json()
        )  # This is AdhocAspectAnalysisResult from api/v1/schemas.py
        logger.success(f"TestingPage: Received ad-hoc analysis results: {results_data}")

        return format_aspect_test_results(results_data)  # Use helper to display

    except httpx.HTTPStatusError as e:
        error_detail = e.response.text
        try:
            error_detail = e.response.json().get("detail", e.response.text)
        except:
            pass
        logger.error(
            f"TestingPage: API HTTP Status Error {e.response.status_code}: {error_detail}",
            exc_info=False,
        )
        return dbc.Alert(
            f"API Error ({e.response.status_code}): {error_detail}",
            color="danger",
            className="mt-3",
        )
    except httpx.RequestError as e:
        logger.error(f"TestingPage: API Connection Error: {e}", exc_info=True)
        return dbc.Alert(
            f"Could not connect to the analysis API: {str(e)}",
            color="danger",
            className="mt-3",
        )
    except Exception as e:
        logger.critical(f"TestingPage: Unexpected error: {str(e)}", exc_info=True)
        return dbc.Alert(
            f"An unexpected error occurred: {str(e)}", color="danger", className="mt-3"
        )
