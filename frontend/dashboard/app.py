import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import sys
from pathlib import Path
from loguru import logger
import re

# --- Path Adjustments ---
DASH_APP_DIR = Path(__file__).resolve().parent  # frontend/dashboard
FRONTEND_DIR = DASH_APP_DIR.parent  # frontend/
PROJECT_ROOT_FOR_DASH_APP = FRONTEND_DIR.parent  # customer_review_analysis/

STANDALONE_DASH_RUN = __name__ == "__main__"

if str(PROJECT_ROOT_FOR_DASH_APP) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_DASH_APP))

if STANDALONE_DASH_RUN:
    if str(FRONTEND_DIR) not in sys.path:  # Add 'frontend' to path
        sys.path.insert(0, str(FRONTEND_DIR))


try:
    from backend.app.config import settings as backend_app_settings

    DASH_MOUNT_URL_PREFIX_FROM_SETTINGS = backend_app_settings.frontend_base_url

    API_HOST = backend_app_settings.backend.host
    if API_HOST == "0.0.0.0":
        API_HOST = "127.0.0.1"  # For local Dash dev
    API_BASE_URL_CONFIG = (
        f"http://{API_HOST}:{backend_app_settings.backend.port}/api/v1"
    )
except ImportError as e:
    logger.warning(
        f"Dash App: Could not import backend_app_settings. Using defaults. Error: {e}"
    )
    DASH_MOUNT_URL_PREFIX_FROM_SETTINGS = "/dashboard"
    API_BASE_URL_CONFIG = "http://127.0.0.1:8000/api/v1"

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
from .pages import products
from .pages import product_detail
from .layout import app_layout_definition


DASH_INTERNAL_URL_BASE = f'{DASH_MOUNT_URL_PREFIX_FROM_SETTINGS.rstrip("/")}/'

app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.LUX, dbc.icons.FONT_AWESOME],
    # url_base_pathname=DASH_INTERNAL_URL_BASE,
    requests_pathname_prefix=DASH_INTERNAL_URL_BASE,
    assets_folder=str(Path(__file__).parent / "assets"),
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
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


logger.debug(
    f"Dash App Initialized: Name='{app.title}', Configured requests_pathname_prefix='{DASH_INTERNAL_URL_BASE}'"
)


app.layout = app_layout_definition


@app.callback(
    Output("page-content", "children"),
    [Input("url", "pathname"), Input("jwt-token-store", "data")],
)
def display_page(pathname: str, jwt_token: str):
    raw_pathname = pathname

    logger.debug(
        f"[Dash Router] Raw pathname from dcc.Location: '{raw_pathname}', JWT present: {bool(jwt_token)}"
    )

    dash_app_prefix = app.config.requests_pathname_prefix
    logger.debug(
        f"[Dash Router] app.config.requests_pathname_prefix: '{dash_app_prefix}'"
    )

    if pathname is None:
        pathname = "/"

    if dash_app_prefix and pathname.startswith(dash_app_prefix):
        relative_pathname = pathname[len(dash_app_prefix) :]
        if not relative_pathname.startswith("/"):
            relative_pathname = "/" + relative_pathname
    else:
        relative_pathname = pathname
        if not relative_pathname.startswith("/"):
            relative_pathname = "/" + relative_pathname

    if not relative_pathname.endswith("/"):
        normalized_relative_pathname = relative_pathname + "/"
    else:
        normalized_relative_pathname = relative_pathname

    logger.debug(
        f"[Dash Router] Relative pathname: '{relative_pathname}', Normalized relative pathname: '{normalized_relative_pathname}'"
    )

    # --- Route Matching using normalized_relative_pathname ---
    if normalized_relative_pathname == "/":
        logger.info(
            f"[Dash Router] Matched Overview page for '{normalized_relative_pathname}' (raw: '{raw_pathname}')"
        )
        return overview.layout
    elif normalized_relative_pathname == "/products/":
        logger.info(
            f"[Dash Router] Matched Products page for '{normalized_relative_pathname}' (raw: '{raw_pathname}')"
        )
        return products.layout
    elif normalized_relative_pathname == "/test-models/":
        logger.info(
            f"[Dash Router] Matched Model Testing page for '{normalized_relative_pathname}' (raw: '{raw_pathname}')"
        )
        return testing.layout

    product_detail_match = re.fullmatch(
        r"/product/([0-9a-fA-F\-]{36})/", normalized_relative_pathname
    )
    if product_detail_match:
        product_id = product_detail_match.group(1)
        logger.info(
            f"[Dash Router] Matched Product Detail page for ID: '{product_id}' from path '{normalized_relative_pathname}' (raw: '{raw_pathname}')"
        )
        return product_detail.layout(product_id=product_id)

    # --- Fallback for No Match ---
    logger.warning(
        f"[Dash Router] Path '{normalized_relative_pathname}' (raw: '{raw_pathname}') was NOT matched. Displaying Dash 404."
    )
    return dbc.Container(
        [
            html.H1("404: Page Not Found in Dash App", className="text-danger"),
            html.Hr(),
            html.P(
                f"The Dash application couldn't find a page for the raw path: {raw_pathname}"
            ),
            html.P(f"It was processed as: {normalized_relative_pathname}"),
            html.P(f"Dash app's base URL prefix is: {dash_app_prefix}"),
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
