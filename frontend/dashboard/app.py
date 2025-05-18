import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import sys
from pathlib import Path
from loguru import logger

# --- Path Adjustments ---
DASH_APP_DIR = Path(__file__).resolve().parent  # frontend/dashboard
FRONTEND_DIR = DASH_APP_DIR.parent  # frontend/
PROJECT_ROOT_FOR_DASH_APP = FRONTEND_DIR.parent  # customer_review_analysis/

STANDALONE_DASH_RUN = __name__ == "__main__"

if str(PROJECT_ROOT_FOR_DASH_APP) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_DASH_APP))
    logger.trace(
        f"Dash App: Added PROJECT_ROOT '{PROJECT_ROOT_FOR_DASH_APP}' to sys.path."
    )

if STANDALONE_DASH_RUN:
    if str(FRONTEND_DIR) not in sys.path:  # Add 'frontend' to path
        sys.path.insert(0, str(FRONTEND_DIR))
        logger.trace(
            f"Dash App (standalone direct run): Added FRONTEND_DIR '{FRONTEND_DIR}' to sys.path for relative imports."
        )


try:
    from backend.app.config import settings as backend_app_settings

    DASH_MOUNT_URL_PREFIX_FROM_SETTINGS = backend_app_settings.frontend_base_url
    if STANDALONE_DASH_RUN:
        logger.info(
            "Dash App (standalone): Successfully imported backend_app_settings."
        )
except ImportError as e:
    logger.warning(
        f"Dash App: Could not import backend_app_settings. Using defaults. Error: {e}"
    )
    DASH_MOUNT_URL_PREFIX_FROM_SETTINGS = "/dashboard"
    if STANDALONE_DASH_RUN:
        try:
            from backend.app.core.logging_config import setup_logging
            from backend.app.config import (
                PROJECT_ROOT as backend_project_root_for_logging,
            )

            minimal_logging_settings = {
                "console_enabled": True,
                "console_level": "DEBUG",
                "file_enabled": False,
                "format": "{time:HH:mm:ss} |DASH_SA| {level} | {message}",
            }
            setup_logging(minimal_logging_settings, backend_project_root_for_logging)
            logger.info(
                "Dash App (standalone): Basic console logging configured (settings import failed)."
            )
        except Exception as log_e:
            print(f"Dash App (standalone): Failed to set up minimal logging: {log_e}")


from .pages import overview, testing
from .layout import app_layout_definition


DASH_INTERNAL_URL_BASE = f'{DASH_MOUNT_URL_PREFIX_FROM_SETTINGS.rstrip("/")}/'

app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.LUX],
    # url_base_pathname=DASH_INTERNAL_URL_BASE,
    requests_pathname_prefix=DASH_INTERNAL_URL_BASE,
    assets_folder=str(Path(__file__).parent / "assets"),
)

app.clientside_callback(
    """
    function(pathname) {
        return window.localStorage.getItem('access_token') || '';
    }
    """,
    Output("jwt-token-store", "data"),
    Input("url", "pathname"),  # triggers on every navigation/page load
)


app.title = "Customer Review Analysis Dashboard"
server = app.server

logger.info(
    f"Dash application initialized. Internal URL base: '{DASH_INTERNAL_URL_BASE}'"
)
logger.debug(
    f"Dash App Initialized: Name='{app.title}', Configured requests_pathname_prefix='{DASH_INTERNAL_URL_BASE}'"
)


app.layout = app_layout_definition


@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname: str):
    logger.info(
        f"[Dash Router] display_page received request for raw browser pathname: '{pathname}'"
    )
    logger.debug(
        f"[Dash Router] Dash app's internal requests_pathname_prefix for comparison: '{app.config.requests_pathname_prefix}'"
    )

    if pathname == app.config.requests_pathname_prefix:
        logger.info(
            f"[Dash Router] Matched overview for '{pathname}'. Serving overview layout."
        )
        return overview.layout
    elif pathname == app.config.requests_pathname_prefix + "test-models":
        logger.info(
            f"[Dash Router] Matched testing page for '{pathname}'. Serving testing layout."
        )
        return testing.layout

    logger.warning(
        f"[Dash Router] Path '{pathname}' was NOT matched by Dash's display_page. Current requests_pathname_prefix: '{app.config.requests_pathname_prefix}'. Displaying Dash 404."
    )
    return dbc.Container(
        [
            html.H1(
                "404: Dash Page Not Matched by display_page", className="text-danger"
            ),
            html.Hr(),
            html.P(
                f"The Dash application's display_page callback didn't find a route for: {pathname}"
            ),
            html.P(
                f"Dash app's requests_pathname_prefix is configured as: {app.config.requests_pathname_prefix}"
            ),
        ],
        fluid=True,
        className="mt-4 text-center",
    )


if STANDALONE_DASH_RUN:  # __name__ == '__main__'
    logger.info(
        f"Running Dash app standalone. Access at: http://127.0.0.1:8050{DASH_INTERNAL_URL_BASE}"
    )
    logger.debug(
        f"Dash app's url_base_pathname is set to: {app.config.url_base_pathname}"
    )

    app.run(debug=True, port=8050, host="127.0.0.1")
