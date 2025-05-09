# Customer Review Analysis Dashboard

A FastAPI backend and Dash frontend for analyzing multilingual customer reviews.

## Project Structure

- `customer_review_analysis/`
  - `backend/`: FastAPI application.
    - `app/`: Core logic, models, services, API endpoints.
      - `data/cache/`: For local caching of analysis results.
      - `data/sample_reviews.csv`: Sample dataset.
      - `prompts/templates/`: Prompt templates.
    - `run.py`: Script to start the backend server.
  - `frontend/`: Dash application.
    - `dashboard/`: Dash app code, pages, assets.
  - `config/`: Configuration files.
    - `settings.yaml`: Main application settings.
  - `requirements.txt`: Python dependencies.
  - `README.md`: This file.

## Setup

1.  **Create & Activate Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # Windows:
    # venv\Scripts\activate
    # macOS/Linux:
    # source venv/bin/activate
    ```

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configuration:**
    - Review and modify `config/settings.yaml` as needed.
      - `backend.dataset_path`: Path to your review dataset.
      - `models`: Configure model types (`local` or `api`), class names, and API endpoints if applicable.
      - `prompts.engine.template_dir`: Path to prompt templates.

## Running the Application

1.  **Start the Backend Server:**
    From the project's root directory (`customer_review_analysis/`):
    ```bash
    python backend/run.py
    ```
    The backend API will be available at `http://<host>:<port>` (e.g., `http://0.0.0.0:8000`).
    - API Docs (Swagger UI): `http://<host>:<port>/docs`
    - Health Check/Root: `http://<host>:<port>/`

2.  **Access the Dashboard:**
    The dashboard is served by the backend at the `frontend_base_url` configured in `settings.yaml`.
    Default: `http://<host>:<port>/dashboard` (e.g., `http://0.0.0.0:8000/dashboard`)

## Key Features

- **Switchable Models:** Easily switch between local model implementations and API-based models via `config/settings.yaml`.
- **Decoupled Architecture:** Backend and frontend are separated, communicating via APIs. Services, models, and configuration are modular.
- **Configuration Driven:** System behavior (model choices, paths, etc.) managed through `settings.yaml`.
- **Caching:** Backend caches dataset analysis results to avoid re-computation on startup (toggleable).
- **Prompt Engine:** Manages system and user prompts with versioning capability (via filename convention or JSON fields).
- **Multilingual Support (Conceptual):** Designed for multilingual reviews with language detection and sentiment analysis models.
- **Dashboard:**
  - **Overview Page:** Displays overall statistics (language distribution, sentiment distribution, sentiment by language) with visualizations.
  - **Model Testing Page:** Allows users to input a review and see live predictions from the configured language and sentiment models.
- **FastAPI Backend:** Serves data APIs and the Dash frontend.
- **Dash Frontend:** Python-based interactive dashboard.

## Development

- **Models:** Implement actual model logic in `backend/app/models/local_models.py` or `api_models.py`. Update `config/settings.yaml` to use your `class` names.
- **Dataset:** Place your review data (CSV format expected, with a 'review_text' column) at the path specified in `backend.dataset_path`.
- **Prompts:** Add or modify JSON prompt templates in `backend/app/prompts/templates/`.
- **Standalone Dash Development:**
  ```bash
  # From customer_review_analysis/
  python frontend/dashboard/app.py
  # Dash will typically run on http://127.0.0.1:8050. Note that API calls will target the URL configured in frontend/dashboard/pages/*.py (defaulting to http://127.0.0.1:8000/api/v1), so the backend should also be running.
