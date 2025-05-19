from dash import html, dcc, callback, Input, Output, State, callback_context
import dash
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
        dbc.Row(
            dbc.Col(
                html.H3("My Review Analysis Dashboard"), width=12, className="mb-3 mt-3"
            )
        ),
        dbc.Row(
            [
                dbc.Col(
                    dcc.Loading(
                        dbc.Card(dbc.CardBody(id="overview-total-reviews-card"))
                    ),
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
                                    dcc.Graph(id="overview-language-chart"),
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
                                    dcc.Graph(id="overview-sentiment-chart"),
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
                                        id="overview-lang-dropdown",
                                        placeholder="Select Language",
                                        className="mb-2",
                                    ),
                                    dcc.Graph(id="overview-sentiment-by-lang-chart"),
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
            id="overview-interval-component", interval=60 * 1000, n_intervals=0
        ),  # Refresh every 60s
        dbc.Button(
            "Refresh Data",
            id="overview-refresh-stats-button",
            color="primary",
            className="mt-2 mb-4 me-2",
        ),
        dbc.Button(
            "Trigger Re-analysis",
            id="overview-trigger-reanalysis-button",
            color="info",
            className="mt-2 mb-4",
        ),
        dcc.Store(id="overview-stats-store"),
        html.Div(id="overview-status-toast-div"),  # For displaying messages
    ],
    fluid=True,
)


def create_placeholder_figure(message="Loading data..."):
    # (Same as your existing function)
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
    [
        Output("overview-stats-store", "data"),
        Output("overview-status-toast-div", "children"),
    ],
    [
        Input("overview-refresh-stats-button", "n_clicks"),
        Input("overview-trigger-reanalysis-button", "n_clicks"),
        Input("overview-interval-component", "n_intervals"),
    ],
    State("jwt-token-store", "data"),
    prevent_initial_call=False,  # Fetch on load
)
def fetch_or_trigger_stats_overview(
    refresh_clicks, trigger_clicks, n_intervals, jwt_token
):
    ctx = callback_context
    triggered_id = (
        ctx.triggered_id if ctx.triggered_id else "overview-interval-component"
    )  # Default to interval for initial load

    headers = {"Authorization": f"Bearer {jwt_token}"} if jwt_token else {}
    toast_message = None

    if triggered_id == "overview-trigger-reanalysis-button":
        logger.info("Overview: Triggering user re-analysis.")
        try:
            response = httpx.post(
                f"{API_BASE_URL}/trigger_user_reanalysis", headers=headers, timeout=10.0
            )
            response.raise_for_status()
            api_data = response.json().get(
                "stats", {}
            )  # Backend returns a status message
            toast_message = dbc.Toast(
                f"Re-analysis triggered: {api_data.get('message', 'Processing...')}",
                header="Information",
                icon="info",
                duration=4000,
                is_open=True,
                style={"position": "fixed", "top": 66, "right": 10, "width": 350},
            )
            # Don't return data yet, let next interval or refresh fetch it
            return dash.no_update, toast_message
        except Exception as e:
            logger.error(f"Overview: Error triggering re-analysis: {e}")
            toast_message = dbc.Toast(
                f"Error triggering re-analysis: {str(e)}",
                header="Error",
                icon="danger",
                duration=4000,
                is_open=True,
                style={"position": "fixed", "top": 66, "right": 10, "width": 350},
            )
            return dash.no_update, toast_message

    # Fetch stats for refresh button or interval
    logger.info(f"Overview: Fetching stats. Trigger: {triggered_id}")
    if not jwt_token:
        logger.warning("Overview: No JWT token, cannot fetch stats.")
        return {"error": "Not authenticated"}, dbc.Toast(
            "Authentication token not found. Please log in.",
            header="Auth Error",
            icon="danger",
            duration=4000,
            is_open=True,
            style={"position": "fixed", "top": 66, "right": 10, "width": 350},
        )
    try:
        response = httpx.get(f"{API_BASE_URL}/stats", headers=headers, timeout=30.0)
        response.raise_for_status()
        stats_data = response.json().get("stats", {})
        logger.success(f"Overview: Successfully fetched stats data.")
        return stats_data, dash.no_update  # No toast on successful regular fetch
    except Exception as e:
        logger.error(f"Overview: Error fetching stats: {e}")
        return {"error": f"API Error: {str(e)}"}, dbc.Toast(
            f"Could not fetch stats: {str(e)}",
            header="API Error",
            icon="danger",
            duration=4000,
            is_open=True,
            style={"position": "fixed", "top": 66, "right": 10, "width": 350},
        )


# --- Callbacks for updating charts (largely similar to your existing ones, but with new IDs) ---
@callback(
    Output("overview-total-reviews-card", "children"),
    Input("overview-stats-store", "data"),
)
def update_total_reviews_card(stats_data):
    if not stats_data or stats_data.get("error"):
        msg = "Loading..."
        if stats_data and stats_data.get("error"):
            msg = stats_data.get("error")
        return [
            html.H4("Status", className="card-title"),
            html.P(msg, className="card-text"),
        ]
    total_processed = stats_data.get("total_reviews_processed", "N/A")
    total_dataset = stats_data.get("total_reviews_in_dataset", "N/A")
    return [
        html.H4(
            f"{total_processed} / {total_dataset}", className="card-title display-6"
        ),
        html.P("Reviews Processed / In Your Dataset", className="card-text"),
    ]


@callback(
    Output("overview-language-chart", "figure"), Input("overview-stats-store", "data")
)
def update_language_chart(stats_data):
    if not stats_data or stats_data.get("error"):
        return create_placeholder_figure(
            stats_data.get("error", "Loading language data...")
        )
    lang_dist = stats_data.get("language_distribution")
    if not lang_dist:
        return create_placeholder_figure("No language data available")
    df = pd.DataFrame(
        list(lang_dist.items()), columns=["Language", "Count"]
    ).sort_values("Count", ascending=False)
    fig = px.bar(df, x="Language", y="Count", color="Language", text_auto=True)
    fig.update_layout(margin=dict(t=20, b=0, l=0, r=0), showlegend=False)
    return fig


@callback(
    Output("overview-sentiment-chart", "figure"), Input("overview-stats-store", "data")
)
def update_sentiment_chart(stats_data):
    if not stats_data or stats_data.get("error"):
        return create_placeholder_figure(
            stats_data.get("error", "Loading sentiment data...")
        )
    sent_dist = stats_data.get("overall_sentiment_distribution")
    if not sent_dist:
        return create_placeholder_figure("No overall sentiment data")
    # Ensure keys are strings for consistent ordering if they are numbers
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
        Output("overview-lang-dropdown", "options"),
        Output("overview-lang-dropdown", "value"),
    ],
    Input("overview-stats-store", "data"),
)
def update_lang_dropdown(stats_data):
    if not stats_data or stats_data.get("error"):
        return [], None
    sent_by_lang = stats_data.get("sentiment_distribution_by_language", {})
    langs = sorted(list(sent_by_lang.keys()))
    options = [
        {"label": lang.upper() if lang else "Unknown", "value": lang} for lang in langs
    ]
    default_value = langs[0] if langs else None
    return options, default_value


@callback(
    Output("overview-sentiment-by-lang-chart", "figure"),
    [Input("overview-stats-store", "data"), Input("overview-lang-dropdown", "value")],
)
def update_sentiment_by_lang_chart(stats_data, selected_language):
    if not stats_data or stats_data.get("error"):
        return create_placeholder_figure(stats_data.get("error", "Loading data..."))
    if not selected_language:
        return create_placeholder_figure("Please select a language")
    sent_by_lang = stats_data.get("sentiment_distribution_by_language", {})
    lang_data = sent_by_lang.get(selected_language)
    if not lang_data:
        return create_placeholder_figure(
            f"No sentiment data for {selected_language.upper()}"
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
