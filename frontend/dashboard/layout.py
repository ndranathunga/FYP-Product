from dash import html, dcc
import dash_bootstrap_components as dbc
import sys
from pathlib import Path

PROJECT_ROOT_PATH_LAYOUT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT_PATH_LAYOUT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_PATH_LAYOUT))

try:
    from backend.app.config import settings as backend_settings

    FRONTEND_BASE_URL = backend_settings.frontend_base_url
except ImportError:
    FRONTEND_BASE_URL = "/dashboard"  # Fallback

base_url_stripped = FRONTEND_BASE_URL.rstrip("/")

navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("Overview", href=f"{base_url_stripped}/")),
        dbc.NavItem(
            dbc.NavLink("Test Models", href=f"{base_url_stripped}/test-models")
        ),
    ],
    brand="Review Analysis Dashboard",
    brand_href=f"{base_url_stripped}/",
    color="primary",
    dark=True,
    className="mb-4",
)

app_layout_definition = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        navbar,
        dbc.Container(id="page-content", fluid=True),  # Page content rendered here
    ]
)
