# frontend/dashboard/pages/product_detail.py
from dash import (
    html,
    dcc,
    callback,
    Input,
    Output,
    State,
    callback_context,
    dash,
)
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import httpx
from loguru import logger
from pathlib import Path
import sys
import json
import pandas as pd  # For potential chart data manipulation
import plotly.express as px  # For aspect summary charts
import plotly.graph_objects as go  # For placeholder

# --- Path Setup & API Base URL (from your existing code) ---
DASH_DETAIL_DIR = Path(__file__).resolve().parent
DASH_APP_DIR_PD = DASH_DETAIL_DIR.parent
FRONTEND_DIR_PD = DASH_APP_DIR_PD.parent
PROJECT_ROOT_FOR_DASH_DETAIL = FRONTEND_DIR_PD.parent

if str(PROJECT_ROOT_FOR_DASH_DETAIL) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_DASH_DETAIL))

try:
    from backend.app.config import settings as backend_settings_detail

    api_host = backend_settings_detail.backend.host
    if api_host == "0.0.0.0":
        api_host = "127.0.0.1"
    API_BASE_URL = f"http://{api_host}:{backend_settings_detail.backend.port}/api/v1"
    FRONTEND_NAV_BASE = backend_settings_detail.frontend_base_url.rstrip("/")
    logger.trace(
        f"ProductDetail Page: API_BASE_URL='{API_BASE_URL}', FRONTEND_NAV_BASE='{FRONTEND_NAV_BASE}'"
    )
except ImportError:
    API_BASE_URL = "http://127.0.0.1:8000/api/v1"
    FRONTEND_NAV_BASE = "/dashboard"
    logger.warning(
        f"ProductDetail Page: Could not import backend_settings. Defaulting API_BASE_URL to {API_BASE_URL}"
    )
# --- End Path Setup ---

# --- Review Modal (from your existing code, looks good) ---
review_modal = dbc.Modal(
    [
        dbc.ModalHeader(dbc.ModalTitle("Add New Review")),
        dbc.ModalBody(
            [
                dbc.Form(
                    [
                        dbc.Label("Review Text:", html_for="pdetail-review-text-input"),
                        dbc.Textarea(
                            id="pdetail-review-text-input",
                            placeholder="Enter customer review text...",
                            className="mb-2",
                            required=True,
                            style={"height": "150px"},
                        ),
                        dbc.Label(
                            "Customer ID (Optional):",
                            html_for="pdetail-review-customer-id-input",
                        ),
                        dbc.Input(
                            id="pdetail-review-customer-id-input",
                            type="text",
                            placeholder="Optional customer identifier",
                            className="mb-2",
                        ),
                    ]
                )
            ]
        ),
        dbc.ModalFooter(
            [
                dbc.Button(
                    "Save Review", id="pdetail-save-review-button", color="primary"
                ),
                dbc.Button(
                    "Cancel", id="pdetail-cancel-review-button", color="secondary"
                ),
            ]
        ),
    ],
    id="pdetail-review-modal",
    is_open=False,
)


# Helper to create placeholder figures
def create_placeholder_figure(message="Loading data..."):
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=16),
    )
    fig.update_layout(
        xaxis_visible=False,
        yaxis_visible=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def layout(product_id=None):  # product_id is passed from app.py router
    if not product_id:
        return dbc.Container(
            dbc.Alert(
                "No product ID specified. Cannot display product details.",
                color="danger",
            ),
            fluid=True,
        )

    return dbc.Container(
        [
            dcc.Store(id="pdetail-product-id-store", data=product_id),
            dcc.Store(
                id="pdetail-product-data-store"
            ),  # To store fetched product details including reviews & aspect summary
            dbc.Row(
                [
                    dbc.Col(
                        html.H3(id="pdetail-product-name-display", className="mt-3"),
                        md=9,
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Back to My Products",
                            href=f"{FRONTEND_NAV_BASE}/products/",
                            color="secondary",
                            outline=True,
                            size="sm",
                        ),
                        md=3,
                        className="text-md-end mt-3 align-self-center",
                    ),
                ]
            ),
            html.P(
                id="pdetail-product-description-display", className="text-muted mb-3"
            ),
            html.Hr(),
            # Section for Product's Dashboard Summary from API
            html.H4("Product Summary Insights", className="mt-4 mb-2"),
            dcc.Loading(html.Div(id="pdetail-dashboard-summary-display")),
            html.Hr(),
            # Section for Aspect Breakdown Chart (Average ratings per aspect for THIS product)
            html.H4("Aspect Performance for this Product", className="mt-4 mb-3"),
            dcc.Loading(dcc.Graph(id="pdetail-aspect-summary-chart")),
            html.Hr(),
            html.H4("Reviews & Aspect Analysis", className="mt-4 mb-3"),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Button(
                            "Add New Review",
                            id="pdetail-add-review-modal-button",
                            color="success",
                            className="mb-3",
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        dbc.Button(
                            [
                                html.I(className="fas fa-sync-alt me-1"),
                                " Refresh Product Data",
                            ],
                            id="pdetail-refresh-product-data-button",
                            color="info",
                            outline=True,
                            className="mb-3",
                        ),
                        width="auto",
                    ),
                ],
                justify="start",
            ),
            html.Div(id="pdetail-status-toast-div"),  # For toasts (save review, errors)
            dcc.Loading(
                html.Div(id="pdetail-review-list-display")
            ),  # Container for review cards
            review_modal,  # The modal for adding a review
        ],
        fluid=True,
    )


# Callback to fetch ALL data for the product (details, reviews, aspect summary)
@callback(
    Output("pdetail-product-data-store", "data"),
    [
        Input("pdetail-product-id-store", "data"),
        Input("pdetail-refresh-product-data-button", "n_clicks"),
    ],
    State("jwt-token-store", "data"),
    prevent_initial_call=False,  # Fetch on initial load with product_id
)
def fetch_full_product_data(product_id, refresh_clicks, jwt_token):
    if not product_id or not jwt_token:
        logger.warning(
            f"ProductDetail: Missing product_id ({product_id}) or JWT for fetching data."
        )
        return {"error": "Product ID or authentication token missing."}

    headers = {"Authorization": f"Bearer {jwt_token}"}
    product_detail_url = (
        f"{API_BASE_URL}/products/{product_id}"  # Endpoint to get ONE product
    )
    # This endpoint in products_reviews.py already populates product.reviews with their analyses

    logger.info(
        f"ProductDetail: Fetching full data for product ID {product_id}. Triggered by: {callback_context.triggered_id}"
    )
    try:
        response = httpx.get(product_detail_url, headers=headers, timeout=20.0)
        response.raise_for_status()
        product_data = (
            response.json()
        )  # This is db_schemas.Product, including list of reviews with their analysis_results

        # Now, we also need the aggregated aspect summary for THIS product from the /stats endpoint
        # The /stats endpoint returns ALL products for the user. We need to extract this one.
        stats_response = httpx.get(
            f"{API_BASE_URL}/stats", headers=headers, timeout=20.0
        )
        stats_response.raise_for_status()
        user_stats_data = stats_response.json()  # This is UserProductsStatsResponse

        specific_product_stats = None
        if user_stats_data and user_stats_data.get("status") == "loaded":
            specific_product_stats = user_stats_data.get("products_data", {}).get(
                str(product_id)
            )

        # Combine product details from /products/{id} and specific stats from /stats
        combined_data = {
            "details": product_data,  # Includes reviews with raw analysis
            "aggregated_summary": specific_product_stats,  # Includes aspects_summary and dashboard_summary
        }
        return combined_data

    except Exception as e:
        logger.error(
            f"ProductDetail: Error fetching full data for product {product_id}: {e}",
            exc_info=True,
        )
        return {"error": f"Failed to load product data: {str(e)}"}


# Callback to display product name and description
@callback(
    [
        Output("pdetail-product-name-display", "children"),
        Output("pdetail-product-description-display", "children"),
    ],
    Input("pdetail-product-data-store", "data"),
)
def display_product_header(combined_data):
    if (
        not combined_data
        or combined_data.get("error")
        or not combined_data.get("details")
    ):
        return "Product Not Found", combined_data.get(
            "error", "Could not load product details."
        )
    product_details = combined_data["details"]
    return product_details.get("name", "N/A"), product_details.get(
        "description", "No description."
    )


# Callback to display the product's dashboard summary
@callback(
    Output("pdetail-dashboard-summary-display", "children"),
    Input("pdetail-product-data-store", "data"),
)
def display_dashboard_summary(combined_data):
    if (
        not combined_data
        or combined_data.get("error")
        or not combined_data.get("aggregated_summary")
    ):
        return dbc.Alert("Product summary data not available.", color="info")

    summary_data = combined_data["aggregated_summary"].get("dashboard_summary", {})
    if not summary_data:
        return dbc.Alert(
            "No dashboard summary information for this product.", color="info"
        )

    current_ratings_list = [
        html.Li(f"{aspect}: {rating:.1f} stars")
        for aspect, rating in summary_data.get("Current Ratings", {}).items()
    ]

    return dbc.Card(
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.H5(
                                    "Average Aspect Ratings:", className="card-title"
                                ),
                                html.Ul(
                                    current_ratings_list
                                    if current_ratings_list
                                    else [html.Li("No aspect ratings calculated.")]
                                ),
                            ],
                            md=6,
                        ),
                        dbc.Col(
                            [
                                html.H5("Textual Summary:", className="card-title"),
                                html.P(summary_data.get("Summary", "N/A")),
                                html.H5("Recommendations:", className="card-title"),
                                html.P(summary_data.get("Recommendations", "N/A")),
                                html.Div(
                                    [
                                        html.Strong("Anomaly Detected: "),
                                        html.Span(
                                            str(summary_data.get("Anomaly", False)),
                                            className=(
                                                "fw-bold text-danger"
                                                if summary_data.get("Anomaly")
                                                else "fw-bold text-success"
                                            ),
                                        ),
                                    ]
                                ),
                            ],
                            md=6,
                        ),
                    ]
                )
            ]
        )
    )


# Callback to display the aspect summary chart for THIS product
@callback(
    Output("pdetail-aspect-summary-chart", "figure"),
    Input("pdetail-product-data-store", "data"),
)
def display_aspect_summary_chart(combined_data):
    if (
        not combined_data
        or combined_data.get("error")
        or not combined_data.get("aggregated_summary")
    ):
        return create_placeholder_figure("Aspect summary data not available.")

    aspect_summary = combined_data["aggregated_summary"].get("aspects_summary", {})
    if not aspect_summary:
        return create_placeholder_figure(
            "No aspect summary calculated for this product."
        )

    chart_data = []
    for aspect_name, details in aspect_summary.items():
        chart_data.append(
            {
                "Aspect": aspect_name,
                "Average Rating": details.get("average_rating", 0),
                "Review Count": details.get("review_count", 0),
            }
        )

    if not chart_data:
        return create_placeholder_figure("No aspect data to plot.")

    df = pd.DataFrame(chart_data).sort_values("Average Rating", ascending=True)
    fig = px.bar(
        df,
        y="Aspect",
        x="Average Rating",
        orientation="h",
        color="Average Rating",
        color_continuous_scale=px.colors.diverging.RdYlGn,
        text="Average Rating",
        title="Average Rating per Aspect for this Product",
        hover_data=["Review Count"],
    )
    fig.update_traces(texttemplate="%{text:.2f} ★", textposition="outside")
    fig.update_layout(
        margin=dict(t=50, b=20, l=150, r=20), yaxis={"categoryorder": "total ascending"}
    )  # Ensure aspect names are fully visible
    return fig


# Callback to display the list of reviews with their aspect analyses
@callback(
    Output("pdetail-review-list-display", "children"),
    Input("pdetail-product-data-store", "data"),
)
def display_reviews_with_aspects(combined_data):
    if (
        not combined_data
        or combined_data.get("error")
        or not combined_data.get("details")
    ):
        return dbc.Alert(
            "Review data not available or error loading product.", color="warning"
        )

    reviews_list = combined_data["details"].get(
        "reviews", []
    )  # reviews is part of Product schema
    if not reviews_list:
        return dbc.Alert(
            "No reviews found for this product yet. Be the first to add one!",
            color="info",
        )

    review_cards = []
    for review_schema in reviews_list:  # review_schema is db_schemas.Review
        review_text = review_schema.get("review_text", "N/A")
        customer_id = review_schema.get("customer_id", "Anonymous")
        created_at = review_schema.get("created_at", "")

        aspect_details_components = [html.Em("Analysis pending or not available.")]
        # analysis_results is db_schemas.AnalysisResultItem (which has result_json)
        analysis_result_item = review_schema.get("analysis_results")
        if analysis_result_item and analysis_result_item.get("result_json"):
            result_json = analysis_result_item["result_json"]
            aspects = result_json.get("aspects", [])
            if aspects:
                aspect_details_components = []
                for aspect in aspects:
                    name = aspect.get("name", "Unknown Aspect")
                    rating = aspect.get("rating", "N/A")
                    justification = aspect.get("justification", "No justification.")
                    if rating == 0:
                        rating = "N/A (Not Mentioned)"  # Clarify 0 rating

                    aspect_details_components.append(
                        dbc.ListGroupItem(
                            [
                                html.Div(
                                    [
                                        html.Strong(f"{name}: "),
                                        html.Span(
                                            (
                                                f"{rating} ★"
                                                if isinstance(rating, (int, float))
                                                and rating > 0
                                                else rating
                                            ),
                                            className=f"fw-bold {'text-success' if isinstance(rating, (int,float)) and rating >=4 else ('text-warning' if isinstance(rating, (int,float)) and rating ==3 else ('text-danger' if isinstance(rating, (int,float)) and rating <3 and rating > 0 else '')) }",
                                        ),
                                    ],
                                    className="d-flex justify-content-between align-items-center",
                                ),
                                html.Small(justification, className="text-muted"),
                            ],
                            className="border-0 ps-0",
                        )
                    )
            else:  # result_json exists but no aspects key
                aspect_details_components = [
                    html.Em("Aspect data not found in analysis result.")
                ]

        review_cards.append(
            dbc.Card(
                className="mb-3",
                children=[
                    dbc.CardBody(
                        [
                            html.Blockquote(
                                className="blockquote mb-0",
                                children=[
                                    html.P(f'"{review_text}"'),
                                    html.Footer(
                                        f"Customer: {customer_id} (on {pd.to_datetime(created_at).strftime('%Y-%m-%d %H:%M') if created_at else 'N/A'})",
                                        className="blockquote-footer",
                                    ),
                                ],
                            ),
                            html.Hr(className="my-2"),
                            html.H6("Aspect Analysis:", className="mt-2 mb-1"),
                            (
                                dbc.ListGroup(aspect_details_components, flush=True)
                                if aspect_details_components
                                else html.P("No aspect details.")
                            ),
                        ]
                    )
                ],
            )
        )
    return (
        dbc.Row([dbc.Col(card) for card in review_cards])
        if review_cards
        else html.P("No reviews to display.")
    )


# --- Callbacks for Review Modal (Open/Close, Save) ---
# (These are similar to your existing product_detail.py, ensure IDs are prefixed with 'pdetail-')
@callback(
    Output("pdetail-review-modal", "is_open"),
    [
        Input("pdetail-add-review-modal-button", "n_clicks"),
        Input("pdetail-cancel-review-button", "n_clicks"),
    ],
    State("pdetail-review-modal", "is_open"),
    prevent_initial_call=True,
)
def toggle_review_modal_pdetail(add_clicks, cancel_clicks, is_open):
    if add_clicks or cancel_clicks:
        return not is_open
    return is_open


@callback(
    [
        Output("pdetail-review-modal", "is_open", allow_duplicate=True),
        Output("pdetail-status-toast-div", "children"),
        Output("pdetail-refresh-product-data-button", "n_clicks"),
    ],  # Trigger refresh
    Input("pdetail-save-review-button", "n_clicks"),
    [
        State("pdetail-product-id-store", "data"),
        State("pdetail-review-text-input", "value"),
        State("pdetail-review-customer-id-input", "value"),
        State("jwt-token-store", "data"),
        State("pdetail-refresh-product-data-button", "n_clicks"),
    ],
    prevent_initial_call=True,
)
def save_new_review_pdetail(
    n_clicks_save,
    product_id,
    review_text,
    customer_id,
    jwt_token,
    current_refresh_clicks,
):
    if not product_id or not jwt_token:
        return (
            False,
            dbc.Toast(
                "Auth/Product ID missing.",
                header="Error",
                icon="danger",
                duration=3000,
                is_open=True,
            ),
            dash.no_update,
        )
    if not review_text:
        return (
            True,
            dbc.Toast(
                "Review text required.",
                header="Validation Error",
                icon="warning",
                duration=3000,
                is_open=True,
            ),
            dash.no_update,
        )

    headers = {"Authorization": f"Bearer {jwt_token}"}
    payload = {"review_text": review_text, "customer_id": customer_id or None}
    toast_content = None
    try:
        response = httpx.post(
            f"{API_BASE_URL}/products/{product_id}/reviews",
            json=payload,
            headers=headers,
            timeout=15.0,
        )
        response.raise_for_status()
        toast_content = dbc.Toast(
            "Review added successfully! Analysis will run in background.",
            header="Success",
            icon="success",
            duration=4000,
            is_open=True,
        )
        return (
            False,
            toast_content,
            (current_refresh_clicks or 0) + 1,
        )  # Close modal, show toast, trigger refresh
    except Exception as e:
        err_msg = str(e)
        if isinstance(e, httpx.HTTPStatusError):
            err_msg = e.response.json().get("detail", str(e))
        logger.error(f"ProductDetail: Error saving review: {err_msg}", exc_info=True)
        toast_content = dbc.Toast(
            f"Error saving review: {err_msg}",
            header="API Error",
            icon="danger",
            duration=4000,
            is_open=True,
        )
        return True, toast_content, dash.no_update  # Keep modal open on error
