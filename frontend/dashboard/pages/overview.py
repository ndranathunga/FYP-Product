# frontend/dashboard/pages/overview.py
from dash import html, dcc, callback, Input, Output, State, callback_context
import dash
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import httpx
from loguru import logger
from pathlib import Path
import sys
from collections import defaultdict  # For aggregating aspect ratings

# --- Path Setup & API Base URL ---
DASH_OVERVIEW_DIR = Path(__file__).resolve().parent
DASH_APP_DIR_O = DASH_OVERVIEW_DIR.parent
FRONTEND_DIR_O = DASH_APP_DIR_O.parent
PROJECT_ROOT_FOR_DASH_OVERVIEW = FRONTEND_DIR_O.parent

if str(PROJECT_ROOT_FOR_DASH_OVERVIEW) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_DASH_OVERVIEW))

try:
    from backend.app.config import settings as backend_settings_overview

    api_host = backend_settings_overview.backend.host
    if api_host == "0.0.0.0":
        api_host = "127.0.0.1"  # For local Dash dev accessing backend
    API_BASE_URL = f"http://{api_host}:{backend_settings_overview.backend.port}/api/v1"
    # Get the base path for Dash links (e.g., /dashboard)
    FRONTEND_NAV_BASE = backend_settings_overview.frontend_base_url.rstrip("/")
    logger.trace(
        f"Overview Page: API_BASE_URL='{API_BASE_URL}', FRONTEND_NAV_BASE='{FRONTEND_NAV_BASE}'"
    )
except ImportError:
    API_BASE_URL = "http://127.0.0.1:8000/api/v1"  # Fallback
    FRONTEND_NAV_BASE = "/dashboard"  # Fallback
    logger.warning(
        f"Overview Page: Could not import backend_settings. Defaulting API_BASE_URL to {API_BASE_URL} and FRONTEND_NAV_BASE to {FRONTEND_NAV_BASE}"
    )
# --- End Path Setup ---


# Helper to create placeholder figures for charts
def create_placeholder_figure(message="Loading data..."):
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=16, color="#888"),
    )
    fig.update_layout(
        xaxis_visible=False,
        yaxis_visible=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=300,  # Default height for placeholders
    )
    return fig


# Function to create a summary card for a product
def create_product_summary_card_overview(
    product_id, product_name, product_dashboard_summary
):
    summary_text = product_dashboard_summary.get(
        "Summary", "No summary available for this product."
    )
    recommendations = product_dashboard_summary.get(
        "Recommendations", "No specific recommendations."
    )
    is_anomaly = product_dashboard_summary.get("Anomaly", False)

    card_color = "danger" if is_anomaly else "light"
    card_border = "danger" if is_anomaly else None

    if is_anomaly:
        card_color = "danger"  # Use for background or text based on theme
        card_border = "border-danger"  # Bootstrap border color class

    # Display key current ratings
    current_ratings = product_dashboard_summary.get("Current Ratings", {})
    ratings_display_items = []
    if current_ratings:
        for aspect, rating in sorted(
            current_ratings.items()
        ):  # Sort for consistent display
            if isinstance(rating, (int, float)):
                ratings_display_items.append(
                    html.Li(f"{aspect}: {rating:.1f} ★", className="small")
                )
    else:
        ratings_display_items.append(
            html.Li("No aspect ratings available.", className="small text-muted")
        )

    card_classes = "mb-3 h-100 shadow-sm"
    if card_border:
        card_classes += f" {card_border}"

    return dbc.Col(
        dbc.Card(
            [
                dbc.CardHeader(html.H5(product_name, className="card-title mb-0")),
                dbc.CardBody(
                    [
                        html.Strong("Summary:", className="card-subtitle"),
                        html.P(summary_text, className="card-text mb-2"),
                        html.Strong(
                            "Avg. Aspect Ratings:", className="card-subtitle small"
                        ),
                        html.Ul(
                            ratings_display_items, className="list-unstyled mb-2 small"
                        ),
                        html.Strong(
                            "Recommendations:", className="card-subtitle small"
                        ),
                        html.P(recommendations, className="card-text small text-muted"),
                        (
                            dbc.Badge(
                                "Anomaly Detected", color="danger", className="me-1"
                            )
                            if is_anomaly
                            else None
                        ),
                    ]
                ),
                dbc.CardFooter(
                    dbc.Button(
                        "View Product Details",
                        href=f"{FRONTEND_NAV_BASE}/product/{product_id}/",  # Ensure FRONTEND_NAV_BASE is defined
                        color="primary",
                        size="sm",
                        outline=True,
                        className="w-100",
                    )
                ),
            ],
            color=card_color,  # Sets background color if not None (e.g., "danger", "light")
            outline=(card_color == "light" or card_color is None) and not card_border,
            className=card_classes,
        ),
        lg=4,
        md=6,
        sm=12,
        className="mb-3",
    )


# Main layout for the overview page
layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H2("My Review Analysis Dashboard"),
                width=12,
                className="mb-3 mt-4 text-center text-primary",
            )
        ),
        dcc.Interval(
            id="overview-interval-component", interval=120 * 1000, n_intervals=0
        ),  # Refresh every 120s
        dbc.Row(
            [
                dbc.Col(
                    dbc.Button(
                        "Refresh Dashboard Data",
                        id="overview-refresh-stats-button",
                        color="primary",
                        className="mb-2 shadow-sm",
                        size="sm",
                    ),
                    width="auto",
                ),
                dbc.Col(
                    dbc.Button(
                        [
                            html.I(className="fas fa-sync-alt me-1"),
                            "Trigger Re-analysis for My Reviews",
                        ],
                        id="overview-trigger-reanalysis-button",
                        color="info",
                        outline=True,
                        className="mb-2 shadow-sm",
                        size="sm",
                    ),
                    width="auto",
                ),
            ],
            className="mb-3",
            justify="center",
        ),
        dcc.Store(
            id="overview-user-stats-store"
        ),  # Stores UserProductsStatsResponse from API
        html.Div(
            id="overview-status-toast-div"
        ),  # For displaying toasts (loading, error, success messages)
        # Overall Summary Cards (Total Products, Total Reviews)
        dbc.Row(
            id="overview-general-summary-cards-row",
            className="mb-3 justify-content-center",
        ),
        html.Hr(className="my-4"),
        # Product Lists: Needs Attention & Good Standing
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H4(
                            [
                                html.I(
                                    className="fas fa-exclamation-triangle me-2 text-danger"
                                ),
                                "Products Needing Attention",
                            ],
                            className="mb-3",
                        ),
                        dcc.Loading(
                            id="loading-attention-products",
                            type="default",
                            children=html.Div(
                                id="overview-attention-products-container"
                            ),
                        ),
                    ],
                    md=6,
                    className="mb-4",
                ),
                dbc.Col(
                    [
                        html.H4(
                            [
                                html.I(className="fas fa-thumbs-up me-2 text-success"),
                                "Products in Good Standing",
                            ],
                            className="mb-3",
                        ),
                        dcc.Loading(
                            id="loading-good-products",
                            type="default",
                            children=html.Div(id="overview-good-products-container"),
                        ),
                    ],
                    md=6,
                    className="mb-4",
                ),
            ]
        ),
        html.Hr(className="my-4"),
        # Overall Aspect Sentiment Chart (Aggregated across user's products)
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H4(
                            [
                                html.I(className="fas fa-chart-bar me-2"),
                                "Overall Aspect Sentiment (Average User-Wide Ratings)",
                            ]
                        ),
                        dcc.Loading(
                            id="loading-aspect-sentiment-chart",
                            type="default",
                            children=dcc.Graph(
                                id="overview-overall-aspect-sentiment-chart"
                            ),
                        ),
                    ],
                    md=12,
                )
            ],
            className="mb-4",
        ),
    ],
    fluid=True,
    className="p-4 bg-light",
)


# Callback to fetch user-specific stats or trigger re-analysis
@callback(
    [
        Output("overview-user-stats-store", "data"),
        Output("overview-status-toast-div", "children"),
    ],
    [
        Input("overview-refresh-stats-button", "n_clicks"),
        Input("overview-trigger-reanalysis-button", "n_clicks"),
        Input("overview-interval-component", "n_intervals"),
    ],
    State("jwt-token-store", "data"),  # Get JWT token from dcc.Store
    prevent_initial_call=False,  # Fetch data on initial page load
)
def fetch_or_trigger_user_stats_overview(
    refresh_clicks, trigger_clicks, n_intervals, jwt_token
):
    ctx = callback_context
    triggered_id = (
        ctx.triggered_id if ctx.triggered_id else "overview-interval-component"
    )  # Default for initial load

    headers = {"Authorization": f"Bearer {jwt_token}"} if jwt_token else {}
    toast_children = []  # List to hold multiple toasts if needed

    if not jwt_token:
        logger.warning(
            "Overview: No JWT token available. Cannot fetch or trigger stats."
        )
        toast_children.append(
            dbc.Toast(
                "Authentication token not found. Please log in to view your dashboard.",
                header="Authentication Error",
                icon="danger",
                duration=5000,
                is_open=True,
                style={
                    "position": "fixed",
                    "top": 20,
                    "right": 20,
                    "zIndex": 1050,
                    "width": 350,
                },
            )
        )
        return {
            "error": "Not authenticated",
            "status": "error",
            "products_data": {},
        }, toast_children

    if triggered_id == "overview-trigger-reanalysis-button":
        logger.info("Overview: User clicked 'Trigger Re-analysis'. Calling API.")
        try:
            response = httpx.post(
                f"{API_BASE_URL}/trigger_user_reanalysis", headers=headers, timeout=15.0
            )
            response.raise_for_status()  # Check for HTTP errors
            api_response_data = (
                response.json()
            )  # Expects UserProductsStatsResponse like structure
            msg = api_response_data.get(
                "message", "Re-analysis successfully initiated in the background."
            )
            toast_children.append(
                dbc.Toast(
                    msg,
                    header="Re-analysis Information",
                    icon="info",
                    duration=4000,
                    is_open=True,
                    style={
                        "position": "fixed",
                        "top": 20,
                        "right": 20,
                        "zIndex": 1050,
                        "width": 350,
                    },
                )
            )
            # No data update needed here for the store, let next refresh/interval pick it up
            return dash.no_update, toast_children
        except Exception as e:
            err_msg = str(e)
            if isinstance(e, httpx.HTTPStatusError):
                err_msg = e.response.json().get("detail", str(e))
            logger.error(
                f"Overview: Error triggering user re-analysis: {err_msg}", exc_info=True
            )
            toast_children.append(
                dbc.Toast(
                    f"Error triggering re-analysis: {err_msg}",
                    header="API Error",
                    icon="danger",
                    duration=5000,
                    is_open=True,
                    style={
                        "position": "fixed",
                        "top": 20,
                        "right": 20,
                        "zIndex": 1050,
                        "width": 350,
                    },
                )
            )
            return dash.no_update, toast_children

    # Fetch stats for initial load, refresh button, or interval
    logger.info(f"Overview: Fetching user stats from API. Triggered by: {triggered_id}")
    try:
        response = httpx.get(
            f"{API_BASE_URL}/stats", headers=headers, timeout=30.0
        )  # This is the user-specific stats endpoint
        api_response_data = (
            response.json()
        )  # This should be UserProductsStatsResponse structure

        if response.status_code != 200 or api_response_data.get("status") == "error":
            error_msg = api_response_data.get(
                "message", f"API Error ({response.status_code}) while fetching stats."
            )
            logger.error(
                f"Overview: Failed to fetch user stats: {error_msg} (HTTP Status: {response.status_code})"
            )
            toast_children.append(
                dbc.Toast(
                    f"Could not load dashboard data: {error_msg}",
                    header="API Error",
                    icon="danger",
                    duration=5000,
                    is_open=True,
                    style={
                        "position": "fixed",
                        "top": 20,
                        "right": 20,
                        "zIndex": 1050,
                        "width": 350,
                    },
                )
            )
            # Ensure the store receives a dict that Dash can serialize, even on error
            return {
                "error": error_msg,
                "status": "error",
                "products_data": {},
            }, toast_children

        logger.success(
            f"Overview: Successfully fetched user stats. API Status: {api_response_data.get('status')}, Message: {api_response_data.get('message')}"
        )
        # api_response_data already contains status, message, products_data, etc.
        return (
            api_response_data,
            dash.no_update,
        )  # No toast for successful regular fetch, unless specific message from API

    except Exception as e:  # Catch httpx.RequestError or other general exceptions
        logger.error(
            f"Overview: General exception while fetching user stats: {e}", exc_info=True
        )
        toast_children.append(
            dbc.Toast(
                f"Could not connect to API or process response: {str(e)}",
                header="Connection/System Error",
                icon="danger",
                duration=5000,
                is_open=True,
                style={
                    "position": "fixed",
                    "top": 20,
                    "right": 20,
                    "zIndex": 1050,
                    "width": 350,
                },
            )
        )
        return {
            "error": f"Exception: {str(e)}",
            "status": "error",
            "products_data": {},
        }, toast_children


# Callback to display general summary cards (total products, total reviews)
@callback(
    Output("overview-general-summary-cards-row", "children"),
    Input("overview-user-stats-store", "data"),
)
def update_overview_general_summary_cards(user_stats_data):
    if not user_stats_data or user_stats_data.get("status") != "loaded":
        status_msg = "Loading summary..."
        if user_stats_data and user_stats_data.get("status") == "error":
            status_msg = user_stats_data.get("message", "Error loading data.")
        elif user_stats_data and user_stats_data.get("status") == "loading":
            status_msg = user_stats_data.get("message", "Initializing...")
        return dbc.Col(dbc.Alert(status_msg, color="info", className="text-center"))

    # These are now user-specific counts from UserProductsStatsResponse
    total_processed = user_stats_data.get("total_reviews_processed_this_user", 0)
    total_dataset_reviews = user_stats_data.get("total_reviews_in_dataset_this_user", 0)
    num_products = len(user_stats_data.get("products_data", {}))

    cards = [
        dbc.Col(
            dbc.Card(
                dbc.CardBody(
                    [
                        html.H4(num_products, className="card-title text-primary"),
                        html.P("My Total Products", className="card-text text-muted"),
                    ]
                ),
                className="text-center shadow-sm",
            ),
            md=4,
            className="mb-3",
        ),
        dbc.Col(
            dbc.Card(
                dbc.CardBody(
                    [
                        html.H4(
                            total_dataset_reviews, className="card-title text-info"
                        ),
                        html.P(
                            "Total Reviews in My Products",
                            className="card-text text-muted",
                        ),
                    ]
                ),
                className="text-center shadow-sm",
            ),
            md=4,
            className="mb-3",
        ),
        dbc.Col(
            dbc.Card(
                dbc.CardBody(
                    [
                        html.H4(total_processed, className="card-title text-success"),
                        html.P(
                            "Reviews with Aspect Analysis",
                            className="card-text text-muted",
                        ),
                    ]
                ),
                className="text-center shadow-sm",
            ),
            md=4,
            className="mb-3",
        ),
    ]
    return cards


# Callback to update the categorized product lists
@callback(
    [
        Output("overview-attention-products-container", "children"),
        Output("overview-good-products-container", "children"),
    ],
    Input("overview-user-stats-store", "data"),
)
def update_categorized_product_lists_overview(user_stats_data):
    if not user_stats_data or user_stats_data.get("status") != "loaded":
        status_msg = "Loading product lists..."
        if user_stats_data and user_stats_data.get("status") == "error":
            status_msg = user_stats_data.get("message", "Error loading products.")
        elif user_stats_data and user_stats_data.get("status") == "loading":
            status_msg = user_stats_data.get("message", "Initializing products...")
        return html.Div(
            dbc.Alert(status_msg, color="secondary", className="text-center")
        ), html.Div(dbc.Alert(status_msg, color="secondary", className="text-center"))

    products_data_dict = user_stats_data.get(
        "products_data", {}
    )  # Dict of product_id -> product_details
    if not products_data_dict:
        api_message = user_stats_data.get(
            "message", "You currently have no products or no review data to display."
        )
        no_data_alert = dbc.Alert(api_message, color="info", className="mt-3")
        return html.Div(no_data_alert), html.Div(no_data_alert)

    attention_products_cards = []
    good_products_cards = []

    for product_id, product_details_dict in products_data_dict.items():
        product_name = product_details_dict.get("product_name", "Unknown Product")
        # dashboard_summary is from ProductOverallStats -> ProductUIDashboardSummary
        dashboard_summary = product_details_dict.get("dashboard_summary", {})

        card_component = create_product_summary_card_overview(
            product_id, product_name, dashboard_summary
        )

        # Categorization logic (can be refined)
        is_attention = dashboard_summary.get("Anomaly", False)
        # Check 'Overall' rating from 'Current Ratings' if available, default to a non-attention state if missing
        overall_rating = dashboard_summary.get("Current Ratings", {}).get("Overall")
        if (
            isinstance(overall_rating, (int, float)) and overall_rating < 3.0
        ):  # Example threshold
            is_attention = True

        if is_attention:
            attention_products_cards.append(card_component)
        else:
            good_products_cards.append(card_component)

    attention_div = (
        dbc.Row(attention_products_cards)
        if attention_products_cards
        else html.P(
            "No products currently flagged for attention. Well done!",
            className="text-center text-muted p-3",
        )
    )
    good_div = (
        dbc.Row(good_products_cards)
        if good_products_cards
        else html.P(
            "No products currently listed in good standing, or all need attention.",
            className="text-center text-muted p-3",
        )
    )

    return attention_div, good_div


# Callback for the aggregated aspect sentiment chart
@callback(
    Output("overview-overall-aspect-sentiment-chart", "figure"),
    Input("overview-user-stats-store", "data"),
)
def update_overall_aspect_sentiment_chart_overview(user_stats_data):
    if not user_stats_data or user_stats_data.get("status") != "loaded":
        return create_placeholder_figure(
            user_stats_data.get("message", "Loading overall aspect sentiment data...")
        )

    products_data_dict = user_stats_data.get("products_data", {})
    if not products_data_dict:
        return create_placeholder_figure(
            "No product data available to aggregate aspect sentiments."
        )

    all_aspects_ratings_aggregated = defaultdict(
        lambda: {"sum_of_weighted_ratings": 0.0, "total_contributing_reviews": 0}
    )

    for _product_id, product_details_dict in products_data_dict.items():
        # aspects_summary is from ProductOverallStats
        aspects_summary_for_product = product_details_dict.get("aspects_summary", {})
        for aspect_name, details in aspects_summary_for_product.items():
            review_count_for_aspect = details.get("review_count", 0)
            if (
                review_count_for_aspect > 0
            ):  # Only consider aspects that have been rated in reviews
                avg_rating_for_aspect = details.get("average_rating", 0.0)
                all_aspects_ratings_aggregated[aspect_name][
                    "sum_of_weighted_ratings"
                ] += (avg_rating_for_aspect * review_count_for_aspect)
                all_aspects_ratings_aggregated[aspect_name][
                    "total_contributing_reviews"
                ] += review_count_for_aspect

    if not all_aspects_ratings_aggregated:
        return create_placeholder_figure(
            "No aspect data found across any of your products."
        )

    chart_df_data = []
    for aspect_name, data in all_aspects_ratings_aggregated.items():
        overall_avg_rating = (
            (data["sum_of_weighted_ratings"] / data["total_contributing_reviews"])
            if data["total_contributing_reviews"] > 0
            else 0.0
        )
        chart_df_data.append(
            {
                "Aspect": aspect_name.capitalize(),
                "Overall Average Rating": overall_avg_rating,
                "Total Contributing Reviews": data["total_contributing_reviews"],
            }
        )

    if not chart_df_data:
        return create_placeholder_figure(
            "No valid aspect ratings to display in the chart."
        )

    df_chart = pd.DataFrame(chart_df_data).sort_values(
        "Overall Average Rating", ascending=False
    )

    fig = px.bar(
        df_chart,
        x="Aspect",
        y="Overall Average Rating",
        color="Overall Average Rating",
        color_continuous_scale=px.colors.diverging.RdYlGn,  # Red-Yellow-Green scale
        range_color=[1, 5],  # Assuming ratings are 1-5
        text="Overall Average Rating",
        hover_data=["Total Contributing Reviews"],
        labels={"Overall Average Rating": "User-Wide Average Rating (1-5 Stars)"},
    )
    fig.update_traces(texttemplate="%{text:.2f} ★", textposition="outside")
    fig.update_layout(
        yaxis_title="Average Rating",
        xaxis_title="Aspect",
        margin=dict(t=30, b=20, l=20, r=20),
        showlegend=False,  # Color bar legend is usually enough
        coloraxis_colorbar=dict(title="Avg. Rating"),
    )
    return fig
