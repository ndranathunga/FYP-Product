from dash import (
    html,
    dcc,
    callback,
    Input,
    Output,
    State,
    callback_context,
)
from dash.exceptions import PreventUpdate
import dash
import dash_bootstrap_components as dbc
import httpx
from loguru import logger
from pathlib import Path
import sys
import json

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

# --- Product Modal ---
product_modal = dbc.Modal(
    [
        dbc.ModalHeader(dbc.ModalTitle(id="product-modal-title")),
        dbc.ModalBody(
            [
                dbc.Input(
                    id="product-id-store", type="hidden"
                ),  # For storing ID during edit
                dbc.Form(
                    [
                        dbc.Label("Product Name:", html_for="product-name-input"),
                        dbc.Input(
                            id="product-name-input",
                            type="text",
                            placeholder="Enter product name",
                            className="mb-2",
                            required=True,
                        ),
                        dbc.Label("Description:", html_for="product-description-input"),
                        dbc.Textarea(
                            id="product-description-input",
                            placeholder="Enter product description",
                            className="mb-2",
                            style={"height": "100px"},
                        ),
                    ]
                ),
            ]
        ),
        dbc.ModalFooter(
            [
                dbc.Button("Save Product", id="save-product-button", color="primary"),
                dbc.Button("Cancel", id="cancel-product-button", color="secondary"),
            ]
        ),
    ],
    id="product-modal",
    is_open=False,
)

layout = dbc.Container(
    [
        html.H3("My Products", className="mt-3 mb-3"),
        dbc.Button(
            "Add New Product",
            id="add-product-open-modal-button",
            color="success",
            className="mb-3",
        ),
        html.Div(id="product-list-toast-div"),  # For status messages
        dcc.Loading(html.Div(id="product-list-container")),
        product_modal,
        dcc.Store(id="force-refresh-product-list-store", data=0),
    ],
    fluid=True,
)


# --- Callback to open and prepare the modal ---
@callback(
    [
        Output("product-modal", "is_open"),
        Output("product-modal-title", "children"),
        Output("product-name-input", "value"),
        Output("product-description-input", "value"),
        Output("product-id-store", "value"),
    ],
    [
        Input("add-product-open-modal-button", "n_clicks"),
        Input(
            "product-list-container", "n_clicks_timestamp"
        ),  #! FIXME: Placeholder for edit clicks if using event delegation
        # For edit, you'd typically have an Input per "edit" button in the list, or use clientside callbacks
        # For simplicity now, we'll assume a more complex setup for edit, or manual ID entry
        Input("cancel-product-button", "n_clicks"),
    ],
    [State("product-modal", "is_open"), State("jwt-token-store", "data")],
    prevent_initial_call=True,
)
def toggle_product_modal(add_clicks, edit_ts, cancel_clicks, is_open, jwt_token):
    ctx = callback_context
    triggered_id = ctx.triggered_id

    if triggered_id == "add-product-open-modal-button":
        return True, "Add New Product", "", "", ""  # Open modal for new product

    # Add logic here if an "edit" button was clicked (more complex to set up without pattern matching callbacks easily)
    # For example, if edit button sets a dcc.Store with the product_id and data, then this callback reads it.

    elif triggered_id == "cancel-product-button":
        return False, "", "", "", ""  # Close modal

    return is_open, dash.no_update, dash.no_update, dash.no_update, dash.no_update


# --- Callback to save product (Create or Update) ---
@callback(
    [
        Output(
            "product-modal", "is_open", allow_duplicate=True
        ),  # Allow duplicate for closing
        Output("product-list-toast-div", "children"),
        Output("force-refresh-product-list-store", "data"),
    ],
    Input("save-product-button", "n_clicks"),
    [
        State("product-name-input", "value"),
        State("product-description-input", "value"),
        State("product-id-store", "value"),  # Check this to see if it's an edit
        State("jwt-token-store", "data"),
        State("force-refresh-product-list-store", "data"),
    ],
    prevent_initial_call=True,
)
def save_product(
    n_clicks, name, description, product_id_to_edit, jwt_token, refresh_count
):
    if not n_clicks:
        raise PreventUpdate
    if not jwt_token:
        return (
            False,
            dbc.Toast(
                "Authentication required.", header="Error", icon="danger", duration=3000
            ),
            dash.no_update,
        )
    if not name:
        return (
            True,
            dbc.Toast(
                "Product name is required.",
                header="Validation Error",
                icon="warning",
                duration=3000,
            ),
            dash.no_update,
        )

    headers = {"Authorization": f"Bearer {jwt_token}"}
    payload = {"name": name, "description": description}
    toast_msg = None
    modal_open_on_error = True  # Keep modal open if save fails

    try:
        if product_id_to_edit:  # This is an UPDATE
            logger.info(f"Products: Updating product ID {product_id_to_edit}")
            response = httpx.put(
                f"{API_BASE_URL}/products/{product_id_to_edit}",
                json=payload,
                headers=headers,
                timeout=10.0,
            )
            action_msg = "updated"
        else:  # This is a CREATE
            logger.info(f"Products: Creating new product: {name}")
            response = httpx.post(
                f"{API_BASE_URL}/products/",
                json=payload,
                headers=headers,
                timeout=10.0,
                follow_redirects=True,
            )
            action_msg = "created"

        response.raise_for_status()
        toast_msg = dbc.Toast(
            f"Product successfully {action_msg}!",
            header="Success",
            icon="success",
            duration=3000,
        )
        return (
            False,
            toast_msg,
            refresh_count + 1,
        )  # Close modal, show success, trigger refresh

    except httpx.HTTPStatusError as e:
        error_detail = e.response.text
        try:
            error_detail = e.response.json().get("detail", e.response.text)
        except json.JSONDecodeError:
            pass

        logger.error(f"Products: HTTP error saving product: {error_detail}")
        toast_msg = dbc.Toast(
            f"Error: {error_detail}", header="API Error", icon="danger", duration=4000
        )
    except Exception as e:
        logger.error(f"Products: Exception saving product: {e}")
        toast_msg = dbc.Toast(
            f"An unexpected error occurred: {str(e)}",
            header="Error",
            icon="danger",
            duration=4000,
        )

    return modal_open_on_error, toast_msg, dash.no_update


# --- Callback to fetch and display product list ---
@callback(
    Output("product-list-container", "children"),
    [
        Input("force-refresh-product-list-store", "data"),  # Triggered by save/delete
        Input("jwt-token-store", "data"),
    ],  # Also trigger if token becomes available (after login)
)
def display_product_list(refresh_trigger, jwt_token):
    if not jwt_token:
        return dbc.Alert("Please log in to view your products.", color="warning")

    headers = {"Authorization": f"Bearer {jwt_token}"}
    try:
        logger.info("Products: Fetching product list.")
        response = httpx.get(
            f"{API_BASE_URL}/products/",
            headers=headers,
            timeout=10.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        products_data = response.json()

        if not products_data:
            return dbc.Alert("You haven't added any products yet.", color="info")

        cards = []
        for p in products_data:
            card_content = [
                dbc.CardHeader(p.get("name")),
                dbc.CardBody(
                    [
                        html.P(
                            p.get("description", "No description."),
                            className="card-text",
                        ),
                        #! FIXME: Placeholder for review count - would need another API call or backend to provide this
                        # html.Small(f"Reviews: {p.get('review_count', 0)}", className="text-muted"),
                    ]
                ),
                dbc.CardFooter(
                    [
                        dbc.Button(
                            "View Details",
                            href=f"/dashboard/product/{p.get('id')}/",
                            color="primary",
                            size="sm",
                            className="me-2",
                        ),
                        # Edit/Delete buttons would need more complex callback logic for ID handling
                        # dbc.Button("Edit", id={"type": "edit-product-btn", "index": p.get("id")}, color="secondary", size="sm", className="me-2"),
                        # dbc.Button("Delete", id={"type": "delete-product-btn", "index": p.get("id")}, color="danger", size="sm"),
                        dbc.Button(
                            "Edit",
                            id=f"edit-prod-{p.get('id')}",
                            color="secondary",
                            size="sm",
                            className="me-2",
                            disabled=True,
                            title="Edit via modal (to be fully implemented)",
                        ),  # Placeholder
                        dbc.Button(
                            "Delete",
                            id=f"del-prod-{p.get('id')}",
                            color="danger",
                            size="sm",
                            disabled=True,
                            title="Delete (to be fully implemented)",
                        ),  # Placeholder
                    ]
                ),
            ]
            cards.append(dbc.Col(dbc.Card(card_content, className="mb-3"), md=4))

        return dbc.Row(cards)

    except httpx.HTTPStatusError as e:
        logger.error(
            f"Products: HTTP status error fetching product list: {e.response.status_code} - {e.request.url}"
        )
        error_message = e.response.text
        try:
            error_message = e.response.json().get("detail", e.response.text)
        except json.JSONDecodeError:
            pass

        if 300 <= e.response.status_code < 400:
            return dbc.Alert(
                f"API Redirect Error: Received {e.response.status_code} for {e.request.url}. Expected a direct response. Details: {error_message}",
                color="danger",
            )
        return dbc.Alert(
            f"Could not load products (HTTP Error {e.response.status_code}): {error_message}",
            color="danger",
        )
    except httpx.RequestError as e:
        logger.error(
            f"Products: Request error fetching product list: {e.request.url} - {e}"
        )
        return dbc.Alert(
            f"Could not load products (Request Error): {str(e)}", color="danger"
        )
    except Exception as e:
        logger.error(f"Products: Generic error fetching product list: {e}")
        return dbc.Alert(f"Could not load products: {str(e)}", color="danger")


# TODO: Implement Callbacks for Edit (populating modal) and Delete product actions
# These are more complex due to needing to identify which product's button was clicked.
# Pattern-matching callbacks or clientside callbacks are often used for this.
