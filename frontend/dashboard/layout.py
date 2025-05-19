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

DASHBOARD_BASE_PATH = FRONTEND_BASE_URL.rstrip("/")

navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("My Dashboard", href=f"{DASHBOARD_BASE_PATH }/")),
        dbc.NavItem(dbc.NavLink("My Products", href=f"{DASHBOARD_BASE_PATH}/products")),
        dbc.NavItem(
            dbc.NavLink("Test Models", href=f"{DASHBOARD_BASE_PATH }/test-models")
        ),
    ],
    brand="Review Analysis Dashboard",
    brand_href=f"{DASHBOARD_BASE_PATH }/",
    color="primary",
    dark=True,
    className="mb-4",
)

app_layout_definition = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="jwt-token-store", storage_type="local"),
        dcc.Store(id="product-list-store"),
        dcc.Store(id="selected-product-id-store"),
        navbar,
        dbc.Container(id="page-content", fluid=True),
    ]
)
