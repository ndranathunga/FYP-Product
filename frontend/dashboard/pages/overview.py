from dash import html, dcc, callback, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import httpx
import dash_bootstrap_components as dbc
import sys
from pathlib import Path
from loguru import logger

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
        api_host = "127.0.0.1"

    API_BASE_URL = f"http://{api_host}:{backend_settings_overview.backend.port}/api/v1"
    logger.trace(
        f"Overview Page: API_BASE_URL set to {API_BASE_URL} from backend settings."
    )
except ImportError as e:
    API_BASE_URL = "http://127.0.0.1:8000/api/v1"  # Fallback
    logger.warning(
        f"Overview Page: Could not import backend_settings. Defaulting API_BASE_URL to {API_BASE_URL}. Error: {e}"
    )


layout = dbc.Container(
    [
        dbc.Row(dbc.Col(html.H3("Dataset Overview"), width=12, className="mb-3 mt-3")),
        dbc.Row(
            [
                dbc.Col(
                    dcc.Loading(dbc.Card(dbc.CardBody(id="total-reviews-card"))),
                    md=4,
                    className="mb-3",
                ),
                dbc.Col(
                    dcc.Loading(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H5(
                                        "Language Distribution", className="card-title"
                                    ),
                                    dcc.Graph(id="language-distribution-chart"),
                                ]
                            )
                        )
                    ),
                    md=8,
                    className="mb-3",
                ),
            ],
            className="mb-2",
        ),
        dbc.Row(
            [
                dbc.Col(
                    dcc.Loading(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H5(
                                        "Overall Sentiment (Stars)",
                                        className="card-title",
                                    ),
                                    dcc.Graph(id="sentiment-distribution-chart"),
                                ]
                            )
                        )
                    ),
                    md=6,
                    className="mb-3",
                ),
                dbc.Col(
                    dcc.Loading(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H5(
                                        "Sentiment by Language", className="card-title"
                                    ),
                                    dcc.Dropdown(
                                        id="lang-dropdown-for-sentiment",
                                        placeholder="Select Language",
                                        className="mb-2",
                                    ),
                                    dcc.Graph(id="sentiment-by-language-chart"),
                                ]
                            )
                        )
                    ),
                    md=6,
                    className="mb-3",
                ),
            ]
        ),
        dcc.Interval(
            id="interval-component-overview", interval=30 * 1000, n_intervals=0
        ),
        dbc.Button(
            "Refresh Data",
            id="refresh-stats-button-overview",
            color="primary",
            className="mt-2 mb-4",
        ),
        html.Div(id="stats-data-store-overview", style={"display": "none"}),
    ],
    fluid=True,
)


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


@callback(
    Output("stats-data-store-overview", "children"),
    [
        Input("refresh-stats-button-overview", "n_clicks"),
        Input("interval-component-overview", "n_intervals"),
    ],
)
def fetch_stats_data_overview(n_clicks, n_intervals):
    triggered_by = (
        callback_context.triggered_id
        if callback_context.triggered_id
        else "initial load/interval"
    )
    logger.debug(
        f"Fetching stats data. Triggered by: {triggered_by}, N_clicks: {n_clicks}, Interval: {n_intervals}"
    )
    try:
        response = httpx.get(f"{API_BASE_URL}/stats", timeout=10.0)
        logger.trace(f"API response status code: {response.status_code} for /stats")
        if response.status_code == 202:
            loading_message = response.json().get("detail", "Stats are loading...")
            logger.info(f"Stats API returned 202 (loading): {loading_message}")
            return {"status": "loading", "message": loading_message}
        response.raise_for_status()
        stats_data = response.json().get("stats", {})
        logger.success(
            f"Successfully fetched stats data. Data keys: {list(stats_data.keys()) if isinstance(stats_data, dict) else 'Not a dict'}"
        )
        return stats_data
    except httpx.RequestError as e:
        logger.error(f"API Connection Error fetching stats: {e}", exc_info=True)
        return {"error": f"API Connection Error: {e}"}
    except httpx.HTTPStatusError as e:
        logger.error(
            f"API HTTP Status Error {e.response.status_code} fetching stats: {e.response.text}",
            exc_info=True,
        )
        return {"error": f"API Error {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        logger.critical(f"Unexpected error fetching stats: {str(e)}", exc_info=True)
        return {"error": f"Unexpected error: {str(e)}"}


@callback(
    Output("total-reviews-card", "children"),
    Input("stats-data-store-overview", "children"),
)
def update_total_reviews_card(stats_data):
    if (
        not stats_data
        or stats_data.get("error")
        or stats_data.get("status") == "loading"
    ):
        msg = "Loading..."
        if stats_data and (stats_data.get("error") or stats_data.get("message")):
            msg = stats_data.get("error") or stats_data.get("message")
        logger.debug(f"Updating total reviews card with status/error: {msg}")
        return [
            html.H4("Status", className="card-title"),
            html.P(msg, className="card-text"),
        ]

    total_processed = stats_data.get("total_reviews_processed", "N/A")
    total_dataset = stats_data.get("total_reviews_in_dataset", "N/A")
    logger.trace(
        f"Updating total reviews card. Processed: {total_processed}, Dataset: {total_dataset}"
    )
    return [
        html.H4(
            f"{total_processed} / {total_dataset}", className="card-title display-6"
        ),
        html.P("Reviews Processed / In Dataset", className="card-text"),
    ]


@callback(
    Output("language-distribution-chart", "figure"),
    Input("stats-data-store-overview", "children"),
)
def update_language_chart(stats_data):
    if (
        not stats_data
        or stats_data.get("error")
        or stats_data.get("status") == "loading"
    ):
        msg = "Loading language data..."
        if stats_data and (stats_data.get("error") or stats_data.get("message")):
            msg = stats_data.get("error") or stats_data.get("message")
        logger.debug(f"Language chart cannot be updated: {msg}")
        return create_placeholder_figure(msg)

    lang_dist = stats_data.get("language_distribution")
    if not lang_dist:
        logger.debug(
            "Language chart: No language distribution data available in stats."
        )
        return create_placeholder_figure("No language data available")
    logger.trace(f"Updating language chart with data: {lang_dist}")
    df = pd.DataFrame(
        list(lang_dist.items()), columns=["Language", "Count"]
    ).sort_values("Count", ascending=False)
    fig = px.bar(df, x="Language", y="Count", color="Language", text_auto=True)
    fig.update_layout(margin=dict(t=20, b=0, l=0, r=0), showlegend=False)
    return fig


@callback(
    Output("sentiment-distribution-chart", "figure"),
    Input("stats-data-store-overview", "children"),
)
def update_sentiment_chart(stats_data):
    if (
        not stats_data
        or stats_data.get("error")
        or stats_data.get("status") == "loading"
    ):
        msg = "Loading sentiment data..."
        if stats_data and (stats_data.get("error") or stats_data.get("message")):
            msg = stats_data.get("error") or stats_data.get("message")
        logger.debug(f"Sentiment chart cannot be updated: {msg}")
        return create_placeholder_figure(msg)

    sent_dist = stats_data.get("overall_sentiment_distribution")
    if not sent_dist:
        logger.debug(
            "Sentiment chart: No overall sentiment distribution data available."
        )
        return create_placeholder_figure("No overall sentiment data")
    logger.trace(f"Updating sentiment chart with data: {sent_dist}")
    df = pd.DataFrame(list(sent_dist.items()), columns=["Stars", "Count"])
    df["Stars"] = df["Stars"].astype(str)
    df = df.sort_values("Stars")
    fig = px.bar(
        df,
        x="Stars",
        y="Count",
        color="Stars",
        text_auto=True,
        color_discrete_map={
            "1": "#d9534f",
            "2": "#f0ad4e",
            "3": "#f0ad4e",
            "4": "#5cb85c",
            "5": "#5cb85c",
        },
    )
    fig.update_layout(margin=dict(t=20, b=0, l=0, r=0), xaxis_title="Star Rating")
    return fig


@callback(
    [
        Output("lang-dropdown-for-sentiment", "options"),
        Output("lang-dropdown-for-sentiment", "value"),
    ],
    Input("stats-data-store-overview", "children"),
)
def update_lang_dropdown(stats_data):
    if (
        not stats_data
        or stats_data.get("error")
        or stats_data.get("status") == "loading"
    ):
        logger.debug(
            "Language dropdown cannot be updated due to missing/error in stats data."
        )
        return [], None
    sent_by_lang = stats_data.get("sentiment_distribution_by_language", {})
    langs = sorted(list(sent_by_lang.keys()))
    options = [
        {"label": lang.upper() if lang else "Unknown", "value": lang} for lang in langs
    ]
    default_value = langs[0] if langs else None
    logger.trace(
        f"Updating language dropdown. Options: {len(options)}, Default: {default_value}"
    )
    return options, default_value


@callback(
    Output("sentiment-by-language-chart", "figure"),
    [
        Input("stats-data-store-overview", "children"),
        Input("lang-dropdown-for-sentiment", "value"),
    ],
)
def update_sentiment_by_lang_chart(stats_data, selected_language):
    if (
        not stats_data
        or stats_data.get("error")
        or stats_data.get("status") == "loading"
    ):
        msg = "Loading data..."
        if stats_data and (stats_data.get("error") or stats_data.get("message")):
            msg = stats_data.get("error") or stats_data.get("message")
        logger.debug(f"Sentiment by language chart cannot be updated: {msg}")
        return create_placeholder_figure(msg)
    if not selected_language:
        logger.debug("Sentiment by language chart: No language selected.")
        return create_placeholder_figure("Please select a language")

    sent_by_lang = stats_data.get("sentiment_distribution_by_language", {})
    lang_data = sent_by_lang.get(selected_language)
    if not lang_data:
        logger.debug(
            f"Sentiment by language chart: No data for selected language '{selected_language}'."
        )
        return create_placeholder_figure(
            f"No sentiment data for {selected_language.upper()}"
        )

    logger.trace(
        f"Updating sentiment by language chart for '{selected_language}'. Data: {lang_data}"
    )
    df = pd.DataFrame(list(lang_data.items()), columns=["Stars", "Count"])
    df["Stars"] = df["Stars"].astype(str)
    df = df.sort_values("Stars")
    fig = px.bar(
        df,
        x="Stars",
        y="Count",
        color="Stars",
        text_auto=True,
        color_discrete_map={
            "1": "#d9534f",
            "2": "#f0ad4e",
            "3": "#f0ad4e",
            "4": "#5cb85c",
            "5": "#5cb85c",
        },
    )
    fig.update_layout(margin=dict(t=20, b=0, l=0, r=0), xaxis_title="Star Rating")
    return fig


from dash import callback_context  # Import callback_context
