# frontend/dashboard/pages/products.py
from dash import (
    html,
    dcc,
    callback,
    Input,
    Output,
    State,
    callback_context,
    ALL,  # For pattern-matching callbacks
)
import dash
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import httpx
from loguru import logger
from pathlib import Path
import sys
import json  # For parsing pattern-matching callback IDs

# --- Path Setup & API Base URL ---
DASH_PRODUCTS_DIR = Path(__file__).resolve().parent
DASH_APP_DIR_P = DASH_PRODUCTS_DIR.parent
FRONTEND_DIR_P = DASH_APP_DIR_P.parent
PROJECT_ROOT_FOR_DASH_PRODUCTS = FRONTEND_DIR_P.parent

if str(PROJECT_ROOT_FOR_DASH_PRODUCTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_DASH_PRODUCTS))

try:
    from backend.app.config import settings as backend_settings_products

    api_host = backend_settings_products.backend.host
    if api_host == "0.0.0.0":
        api_host = "127.0.0.1"
    API_BASE_URL = f"http://{api_host}:{backend_settings_products.backend.port}/api/v1"
    # Get the base path for Dash links (e.g., /dashboard)
    FRONTEND_NAV_BASE = backend_settings_products.frontend_base_url.rstrip("/")
    logger.trace(
        f"Products Page: API_BASE_URL='{API_BASE_URL}', FRONTEND_NAV_BASE='{FRONTEND_NAV_BASE}'"
    )
except ImportError:
    API_BASE_URL = "http://127.0.0.1:8000/api/v1"  # Fallback
    FRONTEND_NAV_BASE = "/dashboard"  # Fallback
    logger.warning(
        f"Products Page: Could not import backend_settings. Defaulting API_BASE_URL to {API_BASE_URL} and FRONTEND_NAV_BASE to {FRONTEND_NAV_BASE}"
    )
# --- End Path Setup ---


# --- Product Modal Definition ---
product_modal = dbc.Modal(
    [
        dbc.ModalHeader(dbc.ModalTitle(id="product-modal-title")),
        dbc.ModalBody(
            [
                # Hidden store for product ID, used to determine if modal is for edit or new
                # Using dcc.Store inside the modal body for this state.
                dcc.Store(id="product-edit-id-store", data=None),
                dbc.Form(
                    [
                        dbc.Label("Product Name:", html_for="product-name-input"),
                        dbc.Input(
                            id="product-name-input",
                            type="text",
                            placeholder="Enter product name",
                            className="mb-3",  # Increased margin-bottom
                            required=True,
                        ),
                        dbc.Label("Description:", html_for="product-description-input"),
                        dbc.Textarea(
                            id="product-description-input",
                            placeholder="Enter product description (optional)",
                            className="mb-2",
                            style={"height": "120px"},  # Slightly taller
                        ),
                    ]
                ),
            ]
        ),
        dbc.ModalFooter(
            [
                dbc.Button(
                    "Save Product",
                    id="save-product-button",
                    color="primary",
                    className="me-1",
                ),
                dbc.Button("Cancel", id="cancel-product-button", color="secondary"),
            ]
        ),
    ],
    id="product-modal",
    is_open=False,
    centered=True,  # Vertically center the modal
    backdrop="static",  # Prevent closing on backdrop click
)

# Main layout for the "My Products" page
layout = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(
                    html.H3("My Products", className="mt-4 mb-3 text-primary"),
                    width=True,
                ),
                dbc.Col(
                    dbc.Button(
                        [
                            html.I(className="fas fa-plus-circle me-2"),
                            "Add New Product",
                        ],
                        id="add-product-open-modal-button",
                        color="success",
                        className="mb-3 float-end shadow-sm",  # Align to the right
                    ),
                    width="auto",
                    className="d-flex align-items-center",
                ),
            ],
            align="center",
        ),
        html.Div(
            id="product-list-toast-div"
        ),  # For displaying status toasts (save, delete, error)
        dcc.Loading(
            id="loading-product-list",
            type="default",  # or "circle", "cube", etc.
            children=html.Div(
                id="product-list-container", className="mt-3"
            ),  # Where product cards will be rendered
        ),
        product_modal,  # The modal component itself
        # This store is used to trigger a refresh of the product list after save/delete actions
        dcc.Store(id="force-refresh-product-list-store", data=0),
    ],
    fluid=True,
    className="p-4",
)


# --- Callback to open modal for "Add New" or prepare for "Edit" ---
@callback(
    [
        Output("product-modal", "is_open"),
        Output("product-modal-title", "children"),
        Output("product-name-input", "value"),
        Output("product-description-input", "value"),
        Output("product-edit-id-store", "data"),
    ],
    [
        Input("add-product-open-modal-button", "n_clicks"),
        Input(
            {"type": "edit-product-dynamic-btn", "index": ALL}, "n_clicks_timestamp"
        ),  # CHANGED to n_clicks_timestamp
        Input("cancel-product-button", "n_clicks"),
    ],
    [
        State("product-modal", "is_open"),
        State("jwt-token-store", "data"),
        # We also need the ID of the button that was clicked if using n_clicks_timestamp
        State({"type": "edit-product-dynamic-btn", "index": ALL}, "id"),
    ],
    prevent_initial_call=True,
)
def handle_product_modal_toggle_and_prepare(
    add_clicks,
    edit_btn_all_timestamps,
    cancel_clicks,  # This is now a list of timestamps
    is_open_current_state,
    jwt_token,
    edit_btn_ids,  # List of ID dicts
):
    ctx = callback_context
    triggered_input_info = ctx.triggered[0] if ctx.triggered else None

    modal_is_open_next_state = is_open_current_state
    modal_title_next_state = dash.no_update
    product_name_next_state = dash.no_update
    product_desc_next_state = dash.no_update
    product_edit_id_next_state = dash.no_update

    if not triggered_input_info:
        # This should not happen if prevent_initial_call=True and an Input fired
        logger.debug("ProductsPage: handle_product_modal_toggle - No trigger info.")
        raise PreventUpdate

    prop_id_str = triggered_input_info["prop_id"]
    triggered_value = triggered_input_info[
        "value"
    ]  # Value of the property that fired (e.g., n_clicks or n_clicks_timestamp)

    # Case 1: "Add New Product" button clicked
    if (
        prop_id_str == "add-product-open-modal-button.n_clicks"
        and add_clicks
        and add_clicks > 0
    ):
        logger.info("ProductsPage: 'Add New Product' button clicked. Opening modal.")
        return True, "Add New Product", "", "", None

    # Case 2: "Cancel Product" button clicked
    elif (
        prop_id_str == "cancel-product-button.n_clicks"
        and cancel_clicks
        and cancel_clicks > 0
    ):
        logger.info("ProductsPage: 'Cancel' button clicked in product modal. Closing.")
        return False, dash.no_update, "", "", None

    # Case 3: One of the dynamic "Edit Product" buttons (using n_clicks_timestamp)
    # n_clicks_timestamp is initially None, then becomes a timestamp on click.
    # We need to find which button in the list of timestamps was actually updated (not None and most recent if multiple were somehow triggered).
    elif ".n_clicks_timestamp" in prop_id_str:
        try:
            id_dict_str = prop_id_str.split(".n_clicks_timestamp")[0]
            id_dict = json.loads(id_dict_str)  # The ID part of the prop_id

            if (
                isinstance(id_dict, dict)
                and id_dict.get("type") == "edit-product-dynamic-btn"
            ):
                # `triggered_value` is the timestamp of the clicked button.
                # `edit_btn_all_timestamps` is the list of all timestamps.
                # We need to find the index of the clicked button using its ID to get its product_id from edit_btn_ids.

                clicked_button_index = -1
                # The `id_dict` from `prop_id_str` IS the ID of the specific button that was clicked.
                product_id_to_edit = id_dict.get("index")

                if (
                    product_id_to_edit and triggered_value is not None
                ):  # A specific edit button was clicked
                    logger.info(
                        f"ProductsPage: Edit button (ID: {id_dict}) clicked for product ID: {product_id_to_edit}. Timestamp: {triggered_value}. Opening modal and fetching data."
                    )

                    name_val, desc_val = "", "Could not load details."
                    if jwt_token:
                        headers = {"Authorization": f"Bearer {jwt_token}"}
                        try:
                            res = httpx.get(
                                f"{API_BASE_URL}/products/{product_id_to_edit}",
                                headers=headers,
                                timeout=7.0,
                            )
                            res.raise_for_status()
                            product_data = res.json()
                            name_val = product_data.get("name", "")
                            desc_val = product_data.get("description", "")
                            logger.debug(
                                f"Fetched data for edit: Name='{name_val}', Desc='{desc_val}'"
                            )
                        except Exception as e:
                            logger.error(
                                f"ProductsPage: Failed to fetch details for product {product_id_to_edit} to edit: {e}",
                                exc_info=True,
                            )
                    else:
                        desc_val = "Authentication token missing."

                    return (
                        True,
                        f"Edit Product (ID: {product_id_to_edit[:8]}...)",
                        name_val,
                        desc_val,
                        product_id_to_edit,
                    )
        except json.JSONDecodeError:
            logger.debug(
                f"ProductsPage: Click from non-JSON ID or non-edit button: {prop_id_str}"
            )
        except Exception as e:
            logger.error(
                f"ProductsPage: Error processing edit button click: {e}", exc_info=True
            )
            return (
                True,
                "Edit Product (Error)",
                "",
                "Error processing click.",
                None,
            )  # Open modal but indicate error

    logger.debug(
        f"ProductsPage: handle_product_modal_toggle - No specific actionable trigger. Triggered prop: {prop_id_str}. Modal open state: {is_open_current_state}"
    )
    return (
        is_open_current_state,
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
    )


# --- Callback to save product (handles both Create and Update) ---
@callback(
    [
        Output("product-modal", "is_open", allow_duplicate=True),
        Output("product-list-toast-div", "children"),
        Output("force-refresh-product-list-store", "data"),
    ],
    Input("save-product-button", "n_clicks"),
    [
        State("product-name-input", "value"),
        State("product-description-input", "value"),
        State("product-edit-id-store", "data"),  # From the dcc.Store in the modal
        State("jwt-token-store", "data"),
        State("force-refresh-product-list-store", "data"),
    ],  # Current value of refresh counter
    prevent_initial_call=True,
)
def save_product(
    n_clicks_save,
    product_name,
    product_description,
    product_id_being_edited,
    jwt_token,
    current_refresh_count,
):
    if not n_clicks_save:  # Should not happen due to prevent_initial_call=True
        raise PreventUpdate

    toast_style = {
        "position": "fixed",
        "top": 20,
        "right": 20,
        "zIndex": 1050,
        "width": 350,
    }

    if not jwt_token:
        return (
            False,
            dbc.Toast(
                "Authentication required to save product.",
                header="Auth Error",
                icon="danger",
                duration=4000,
                is_open=True,
                style=toast_style,
            ),
            dash.no_update,
        )
    if not product_name or not product_name.strip():
        # Keep modal open for user to correct
        return (
            True,
            dbc.Toast(
                "Product name is required.",
                header="Validation Error",
                icon="warning",
                duration=4000,
                is_open=True,
                style=toast_style,
            ),
            dash.no_update,
        )

    headers = {"Authorization": f"Bearer {jwt_token}"}
    # ProductUpdate schema from backend expects name, description (both optional for update)
    # ProductCreate schema expects name (required), description (optional)
    payload = {"name": product_name, "description": product_description or None}

    toast_children = []
    modal_should_be_open = True  # Keep modal open on error by default
    next_refresh_count = dash.no_update

    try:
        if product_id_being_edited:  # This is an UPDATE operation
            logger.info(
                f"ProductsPage: Attempting to update product ID {product_id_being_edited} with name '{product_name}'"
            )
            # ProductUpdate schema on backend handles partial updates if fields are Optional
            response = httpx.put(
                f"{API_BASE_URL}/products/{product_id_being_edited}",
                json=payload,
                headers=headers,
                timeout=10.0,
            )
            action_message = "updated"
        else:  # This is a CREATE operation
            logger.info(
                f"ProductsPage: Attempting to create new product with name '{product_name}'"
            )
            # ProductCreate schema on backend
            response = httpx.post(
                f"{API_BASE_URL}/products/", json=payload, headers=headers, timeout=10.0
            )
            action_message = "created"

        response.raise_for_status()  # Raise an exception for 4xx/5xx errors

        toast_children.append(
            dbc.Toast(
                f"Product successfully {action_message}!",
                header="Success!",
                icon="success",
                duration=3000,
                is_open=True,
                style=toast_style,
            )
        )
        modal_should_be_open = False  # Close modal on success
        next_refresh_count = (
            current_refresh_count or 0
        ) + 1  # Trigger product list refresh

    except httpx.HTTPStatusError as e:
        error_detail = e.response.text
        try:
            error_detail = e.response.json().get("detail", e.response.text)
        except json.JSONDecodeError:
            pass
        logger.error(
            f"ProductsPage: HTTP error saving product: {error_detail} (Status: {e.response.status_code})",
            exc_info=True,
        )
        toast_children.append(
            dbc.Toast(
                f"API Error: {error_detail}",
                header=f"Error (Status {e.response.status_code})",
                icon="danger",
                duration=5000,
                is_open=True,
                style=toast_style,
            )
        )
    except Exception as e:
        logger.error(
            f"ProductsPage: Unexpected exception saving product: {e}", exc_info=True
        )
        toast_children.append(
            dbc.Toast(
                f"An unexpected error occurred: {str(e)}",
                header="System Error",
                icon="danger",
                duration=5000,
                is_open=True,
                style=toast_style,
            )
        )

    return modal_should_be_open, toast_children, next_refresh_count


# --- Callback to fetch and display product list ---
@callback(
    Output("product-list-container", "children"),
    [
        Input("force-refresh-product-list-store", "data"),  # Triggered by save/delete
        Input("jwt-token-store", "data"),
    ],  # Also trigger if token becomes available (e.g., after login)
    # prevent_initial_call=False # Allow to run on page load if JWT is present
)
def display_product_list(refresh_trigger_count, jwt_token):
    if not jwt_token:
        return dbc.Alert(
            "Please log in to view your products.",
            color="warning",
            className="mt-3 text-center",
        )

    headers = {"Authorization": f"Bearer {jwt_token}"}
    logger.info(
        f"ProductsPage: Fetching product list. Refresh trigger: {refresh_trigger_count}"
    )
    try:
        response = httpx.get(f"{API_BASE_URL}/products/", headers=headers, timeout=10.0)
        response.raise_for_status()  # Check for HTTP errors
        products_data_list = response.json()  # Expects List[db_schemas.Product]

        if not products_data_list:
            return dbc.Alert(
                "You haven't added any products yet. Click 'Add New Product' to start!",
                color="info",
                className="mt-3 text-center",
            )

        product_cards = []
        for (
            product_item
        ) in products_data_list:  # product_item is a dict matching db_schemas.Product
            product_id = product_item.get("id")

            # Define a unique ID for each edit button using pattern-matching ID structure
            edit_button_id_dict = {
                "type": "edit-product-dynamic-btn",
                "index": str(product_id),
            }
            # Delete button would be similar: {"type": "delete-product-dynamic-btn", "index": str(product_id)}

            # Get review count (assuming 'reviews' list is part of the Product schema from backend)
            review_count = int(product_item.get("review_count", 0))

            card_content = [
                dbc.CardHeader(
                    html.H5(
                        product_item.get("name", "Unnamed Product"),
                        className="mb-0 card-title",
                    )
                ),
                dbc.CardBody(
                    [
                        html.P(
                            product_item.get("description", "No description provided."),
                            className="card-text text-muted",
                        ),
                        html.Small(f"Reviews: {review_count}", className="text-info"),
                    ]
                ),
                dbc.CardFooter(
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Button(
                                    [html.I(className="fas fa-eye me-1"), "Details"],
                                    href=f"{FRONTEND_NAV_BASE}/product/{product_id}/",
                                    color="primary",
                                    size="sm",
                                    outline=True,
                                    className="w-100",
                                ),
                                width=6,
                                className="pe-1",
                            ),
                            dbc.Col(
                                dbc.Button(
                                    [html.I(className="fas fa-edit me-1"), "Edit"],
                                    id=edit_button_id_dict,
                                    color="secondary",
                                    size="sm",
                                    outline=True,
                                    className="w-100",
                                ),
                                width=6,
                                className="ps-1",
                            ),
                            # TODO: Add a delete button and its callback logic
                            # dbc.Col(dbc.Button([html.I(className="fas fa-trash-alt me-1"), "Delete"], id={"type":"delete-product-dynamic-btn", "index": product_id}, color="danger", size="sm", outline=True, className="w-100 mt-1"), width=12),
                        ],
                        className="gx-2",
                    )  # gx-2 for gutter spacing between columns
                ),
            ]
            product_cards.append(
                dbc.Col(
                    dbc.Card(card_content, className="mb-4 shadow-sm h-100"),
                    xl=3,
                    lg=4,
                    md=6,
                    sm=12,
                )
            )  # Responsive grid

        return (
            dbc.Row(product_cards, className="mt-2")
            if product_cards
            else html.P("No products to display.", className="text-center")
        )

    except httpx.HTTPStatusError as e:
        error_message = e.response.text
        try:
            error_message = e.response.json().get("detail", e.response.text)
        except:
            pass
        logger.error(
            f"ProductsPage: HTTP error fetching product list: {error_message} (Status: {e.response.status_code})",
            exc_info=True,
        )
        return dbc.Alert(
            f"Could not load products (API Error {e.response.status_code}): {error_message}",
            color="danger",
            className="mt-3",
        )
    except Exception as e:
        logger.error(
            f"ProductsPage: Generic error fetching product list: {e}", exc_info=True
        )
        return dbc.Alert(
            f"Could not load products: {str(e)}", color="danger", className="mt-3"
        )


# TODO: Implement Callbacks for Delete product actions if you add delete buttons.
# This would involve:
# 1. A pattern-matching Input for delete buttons: Input({"type": "delete-product-dynamic-btn", "index": ALL}, "n_clicks")
# 2. An API call to DELETE /products/{product_id}
# 3. A confirmation modal (dbc.Modal with "Are you sure?" message)
# 4. Updating "force-refresh-product-list-store" to refresh the list.
