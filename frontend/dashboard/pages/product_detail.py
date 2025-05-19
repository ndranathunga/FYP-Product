from dash import (
    html,
    dcc,
    callback,
    Input,
    Output,
    State,
)
from dash.exceptions import PreventUpdate
import dash
import dash_bootstrap_components as dbc
import httpx
from loguru import logger
from pathlib import Path
import sys

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

# --- Review Modal ---
review_modal = dbc.Modal(
    [
        dbc.ModalHeader(dbc.ModalTitle("Add New Review")),
        dbc.ModalBody(
            [
                dbc.Form(
                    [
                        dbc.Label("Review Text:", html_for="review-text-input"),
                        dbc.Textarea(
                            id="review-text-input",
                            placeholder="Enter customer review text...",
                            className="mb-2",
                            required=True,
                            style={"height": "150px"},
                        ),
                        dbc.Label(
                            "Customer ID (Optional):",
                            html_for="review-customer-id-input",
                        ),
                        dbc.Input(
                            id="review-customer-id-input",
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
                dbc.Button("Save Review", id="save-review-button", color="primary"),
                dbc.Button("Cancel", id="cancel-review-button", color="secondary"),
            ]
        ),
    ],
    id="review-modal",
    is_open=False,
)


def layout(product_id=None):
    if not product_id:
        return dbc.Container(
            dbc.Alert("No product ID specified.", color="danger"), fluid=True
        )

    return dbc.Container(
        [
            dcc.Store(
                id="pdetail-product-id-store", data=product_id
            ),  # Store the product ID
            dbc.Row(
                [
                    dbc.Col(html.H3(id="pdetail-product-name", className="mt-3"), md=9),
                    dbc.Col(
                        dbc.Button(
                            "Back to Products",
                            href="/dashboard/products/",
                            color="link",
                        ),
                        md=3,
                        className="text-md-end mt-3",
                    ),
                ]
            ),
            html.P(id="pdetail-product-description", className="lead"),
            html.Hr(),
            html.H4("Reviews for this Product", className="mt-4 mb-3"),
            dbc.Button(
                "Add New Review",
                id="add-review-open-modal-button",
                color="success",
                className="mb-3",
            ),
            html.Div(id="pdetail-review-list-toast-div"),
            dcc.Loading(html.Div(id="pdetail-review-list-container")),
            review_modal,
            dcc.Store(id="force-refresh-review-list-store", data=0),
            dcc.Interval(
                id="pdetail-review-refresh-interval", interval=15 * 1000, n_intervals=0
            ),  # Refresh reviews periodically for analysis updates
        ],
        fluid=True,
    )


# --- Callback to fetch product details ---
@callback(
    [
        Output("pdetail-product-name", "children"),
        Output("pdetail-product-description", "children"),
    ],
    [
        Input("pdetail-product-id-store", "data"),  # Triggered when product_id is set
        Input("jwt-token-store", "data"),
    ],
)
def load_product_details(product_id, jwt_token):
    if not product_id or not jwt_token:
        raise PreventUpdate

    headers = {"Authorization": f"Bearer {jwt_token}"}
    try:
        logger.info(f"ProductDetail: Fetching details for product ID {product_id}")
        response = httpx.get(
            f"{API_BASE_URL}/products/{product_id}", headers=headers, timeout=10.0
        )
        response.raise_for_status()
        product_data = response.json()
        return product_data.get("name", "Product Name"), product_data.get(
            "description", "No description."
        )
    except Exception as e:
        logger.error(
            f"ProductDetail: Error fetching product details for {product_id}: {e}"
        )
        return f"Error loading product: {product_id}", str(e)


# --- Callback to open review modal ---
@callback(
    Output("review-modal", "is_open"),
    [
        Input("add-review-open-modal-button", "n_clicks"),
        Input("cancel-review-button", "n_clicks"),
    ],
    State("review-modal", "is_open"),
    prevent_initial_call=True,
)
def toggle_review_modal(add_clicks, cancel_clicks, is_open):
    if add_clicks or cancel_clicks:
        return not is_open
    return is_open


# --- Callback to save a new review ---
@callback(
    [
        Output("review-modal", "is_open", allow_duplicate=True),
        Output("pdetail-review-list-toast-div", "children"),
        Output(
            "force-refresh-review-list-store", "data"
        ),  # Trigger review list refresh
        Output("review-text-input", "value"),
        Output("review-customer-id-input", "value"),
    ],
    Input("save-review-button", "n_clicks"),
    [
        State("pdetail-product-id-store", "data"),
        State("review-text-input", "value"),
        State("review-customer-id-input", "value"),
        State("jwt-token-store", "data"),
        State("force-refresh-review-list-store", "data"),
    ],
    prevent_initial_call=True,
)
def save_new_review(
    n_clicks, product_id, review_text, customer_id, jwt_token, refresh_count
):
    if not product_id or not jwt_token:
        return (
            False,
            dbc.Toast(
                "Error: Missing product ID or authentication.",
                header="Error",
                icon="danger",
            ),
            dash.no_update,
            "",
            "",
        )
    if not review_text:
        return (
            True,
            dbc.Toast(
                "Review text cannot be empty.",
                header="Validation Error",
                icon="warning",
            ),
            dash.no_update,
            review_text,
            customer_id,
        )

    headers = {"Authorization": f"Bearer {jwt_token}"}
    payload = {"review_text": review_text, "customer_id": customer_id or None}
    toast_msg = None
    modal_open_on_error = True

    try:
        logger.info(f"ProductDetail: Saving review for product {product_id}")
        response = httpx.post(
            f"{API_BASE_URL}/products/{product_id}/reviews",
            json=payload,
            headers=headers,
            timeout=10.0,
        )
        response.raise_for_status()
        toast_msg = dbc.Toast(
            "Review added! Analysis will begin shortly.",
            header="Success",
            icon="success",
            duration=4000,
        )
        return (
            False,
            toast_msg,
            refresh_count + 1,
            "",
            "",
        )  # Close modal, show success, trigger refresh, clear form
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", "Failed to save review.")
        logger.error(f"ProductDetail: HTTP error saving review: {error_detail}")
        toast_msg = dbc.Toast(
            f"Error: {error_detail}", header="API Error", icon="danger", duration=4000
        )
    except Exception as e:
        logger.error(f"ProductDetail: Exception saving review: {e}")
        toast_msg = dbc.Toast(
            f"An unexpected error occurred: {str(e)}",
            header="Error",
            icon="danger",
            duration=4000,
        )

    return modal_open_on_error, toast_msg, dash.no_update, review_text, customer_id


# --- Callback to fetch and display reviews for the product ---
@callback(
    Output("pdetail-review-list-container", "children"),
    [
        Input("force-refresh-review-list-store", "data"),
        Input("pdetail-review-refresh-interval", "n_intervals"),
        Input("pdetail-product-id-store", "data"),
        Input("jwt-token-store", "data"),
    ],
)
def display_review_list(refresh_trigger, interval_trigger, product_id, jwt_token):
    if not product_id or not jwt_token:
        return dbc.Alert("Product ID missing or not authenticated.", color="warning")

    headers = {"Authorization": f"Bearer {jwt_token}"}
    try:
        # logger.debug(f"ProductDetail: Fetching reviews for product {product_id}. Trigger: {callback_context.triggered_id}")
        response = httpx.get(
            f"{API_BASE_URL}/products/{product_id}/reviews",
            headers=headers,
            timeout=10.0,
        )
        response.raise_for_status()
        reviews_data = response.json()

        if not reviews_data:
            return dbc.Alert(
                "No reviews yet for this product. Add one!",
                color="info",
                className="mt-3",
            )

        review_items = []
        for r in reviews_data:
            analysis = r.get("analysis_results")
            analysis_display = "Analysis pending..."
            if analysis:
                lang = analysis.get("language", "N/A")
                sentiment = analysis.get("sentiment", "N/A")
                confidence = analysis.get("confidence", None)
                conf_str = f"{confidence:.2f}" if confidence is not None else "N/A"
                analysis_display = html.Div(
                    [
                        html.Strong("Lang: "),
                        f"{lang.upper()}",
                        html.Strong(" Sent: "),
                        f"{sentiment} ★",
                        html.Strong(" Conf: "),
                        conf_str,
                    ],
                    className="small text-muted",
                )

            review_card = dbc.Card(
                dbc.CardBody(
                    [
                        html.P(
                            f"\"{r.get('review_text')}\"",
                            className="card-text fst-italic",
                        ),
                        html.P(
                            f"Customer ID: {r.get('customer_id', 'N/A')}",
                            className="small",
                        ),
                        analysis_display,
                        # html.Pre(json.dumps(r, indent=2), className="small bg-light p-2 mt-2") # For debugging
                    ]
                ),
                className="mb-3",
            )
            review_items.append(review_card)

        return html.Div(review_items)

    except Exception as e:
        logger.error(f"ProductDetail: Error fetching reviews for {product_id}: {e}")
        return dbc.Alert(
            f"Could not load reviews: {str(e)}", color="danger", className="mt-3"
        )
