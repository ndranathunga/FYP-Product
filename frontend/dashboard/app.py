import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import sys
from pathlib import Path
from loguru import logger

DASH_APP_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = DASH_APP_DIR.parent
PROJECT_ROOT_FOR_DASH_APP = FRONTEND_DIR.parent

STANDALONE_DASH_RUN = __name__ == "__main__"

if str(PROJECT_ROOT_FOR_DASH_APP) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_DASH_APP))

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
    if (
        STANDALONE_DASH_RUN
    ):  # If running standalone and config failed, setup basic logging for Dash
        from backend.app.core.logging_config import (
            setup_logging,
        )  # Try to import for standalone
        from backend.app.config import PROJECT_ROOT

        # Create a minimal logging config for standalone Dash if main one failed
        minimal_logging_settings = {
            "console_enabled": True,
            "console_level": "DEBUG",
            "file_enabled": False,
            "format": "{time:HH:mm:ss} |DASH| {level} | {message}",
        }
        setup_logging(minimal_logging_settings, PROJECT_ROOT)
        logger.info(
            "Dash App (standalone): Basic console logging configured due to settings import failure."
        )


from .pages import overview, testing
from .layout import app_layout_definition

DASH_INTERNAL_URL_BASE = f'{DASH_MOUNT_URL_PREFIX_FROM_SETTINGS.rstrip("/")}/'

app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.LUX],
    url_base_pathname=DASH_INTERNAL_URL_BASE,
    assets_folder=str(Path(__file__).parent / "assets"),
)
app.title = "Customer Review Analysis Dashboard"
server = app.server
logger.info(
    f"Dash application initialized. Internal URL base: '{DASH_INTERNAL_URL_BASE}'"
)

app.layout = app_layout_definition


@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname: str):
    logger.debug(f"[Dash Router] Pathname received: '{pathname}' for display_page.")
    if pathname == DASH_INTERNAL_URL_BASE + "test-models":
        logger.debug("[Dash Router] Routing to 'testing' page.")
        return testing.layout
    elif pathname == DASH_INTERNAL_URL_BASE:
        logger.debug("[Dash Router] Routing to 'overview' page.")
        return overview.layout

    logger.warning(f"[Dash Router] Path '{pathname}' not recognized. Displaying 404.")
    return dbc.Container(
        [
            html.H1("404: Dash Page Not Found", className="text-danger"),
            html.Hr(),
            html.P(f"The Dash application doesn't have a page for path: {pathname}"),
        ],
        fluid=True,
        className="mt-4 text-center",
    )


if STANDALONE_DASH_RUN:
    logger.info(
        f"Running Dash app standalone. Access at: http://127.0.0.1:8050{DASH_INTERNAL_URL_BASE}"
    )
    logger.debug(
        f"Dash app's url_base_pathname is set to: {app.config.url_base_pathname}"
    )
    app.run_server(debug=True, port=8050)
