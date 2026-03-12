# Experiment Tracking System

## Project Overview

This project is a comprehensive **Experiment Tracking System** built with **Streamlit** and **SQLAlchemy**. It is designed to manage laboratory workflows, track experimental conditions, store results, and maintain an inventory of samples and chemicals.

The application serves as a central hub for researchers to:
- Log new experiments and conditions.
- Track sample inventory and history.
- Manage chemical compounds and additives.
- View and analyze experimental results.
- Perform bulk data uploads via Excel templates.
- Monitor reactor status via a dashboard.

## Architecture

The project follows a modular architecture separating the frontend presentation logic from the backend data models.

### Frontend (Streamlit)
- **Entry Point:** `app.py` handles the main application layout, routing, and authentication.
- **Components:** `frontend/components/` contains modular UI components for different pages (e.g., `new_experiment.py`, `view_experiments.py`, `bulk_uploads.py`).
- **Configuration:** `frontend/config/variable_config.py` centralizes UI configuration, field types, and default values to ensure consistency.

### Backend (SQLAlchemy + SQLite)
- **Database:** Uses SQLite for data storage, managed via SQLAlchemy ORM.
- **Models:** The database schema is defined in `database/models/` and is modularized:
  - `experiments.py`: Core experiment definitions, notes, and logs.
  - `conditions.py`: Experimental parameters and setup conditions.
  - `results.py`: Storage for scalar results, ICP data, and other metrics.
  - `samples.py`: Sample inventory and metadata.
  - `chemicals.py`: Chemical compound management.
  - `analysis.py` & `xrd.py`: External analysis data (XRD, Elemental, etc.).
  - `enums.py`: Controlled vocabulary (Enums) for consistent data entry.
- **Migrations:** Database schema changes are managed using **Alembic**.

### Bulk Uploads Logic (`backend/services/bulk_uploads/`)
- **`new_experiments.py`**: Handles creation of experiments, conditions, and additives via multi-sheet Excel templates. Supports complex experiment ID parsing (lineage, treatments) and auto-copying of conditions from parent experiments.
- **`scalar_results.py`**: Manages upload of solution chemistry data (pH, conductivity, dissolved oxygen, etc.) via Excel. Supports partial updates, row-level validation, and integration with `ScalarResultsService`.
- **`icp_service.py`**: Processes raw instrument CSV exports from ICP-OES. Includes delimiter detection, blank filtering, dilution correction, and automatic extraction of metadata from sample labels.
- **`actlabs_titration_data.py` / `actlabs_xrd_report.py`**: Specialized parsers for importing external lab reports (titration, XRD).
- **`aeris_xrd.py`**: Handles time-series XRD data from Aeris instruments, linking scans to specific experiment timepoints.
- **`pxrf_data.py`**: Uploads portable XRF readings from Excel.
- **`rock_inventory.py`**: Bulk upsert for geological samples, including photo attachment.
- **`chemical_inventory.py`**: Manages the chemical compound database via Excel upload.
- **`experiment_status.py`**: Bulk updates for experiment status (e.g., marking batches as ONGOING/COMPLETED) and reactor assignment.
- **`quick_upload.py`**: Framework for metric-specific mini-templates (e.g., just uploading pH data without other fields).
- **`long_format.py`**: Advanced parser for "long format" data (one row per measurement) to support LIMS integration and programmatic uploads.

### Key Utilities
- **`utils.py`**: Contains shared helper functions and business logic.
- **`utils/auto_updater.py`**: Handles the automated deployment and update process on the production server.
- **`utils/database_backup.py`**: Manages automated database backups and public read-only copies.

## Deployment Status & Workflow

The system operates across two distinct environments:

### 1. Development Environment (Personal Work Computer)
- **Role:** Primary development, testing, and schema design.
- **Database:** Uses a local development database.
- **Workflow:** Code changes are developed, tested locally (including migrations), and pushed to GitHub.

### 2. Production Environment (Lab PC)
- **Role:** Hosting the live Streamlit application for lab users.
- **Database:** Maintains the authoritative production database (`experiments.db`).
- **Update Mechanism:** Uses a custom **Auto-Updater** (`auto_update.bat`).
  - **Polling:** Checks GitHub for updates every 5 minutes (or as scheduled).
  - **Process:**
    1.  Detects new commits on `main`.
    2.  Creates a timestamped backup of the production database.
    3.  Pulls the latest code.
    4.  Installs new dependencies.
    5.  Runs `alembic upgrade head` to apply schema migrations.
    6.  Restarts the Streamlit application.
  - **Safety:** If an update fails, it automatically rolls back the code and restores the database backup.

### Backup Strategy
- **Daily Backups:** Automated backups run every 24 hours with a 30-day retention policy.
- **Public Copies:** A read-only copy of the database is generated every 12 hours for external analysis/reporting (e.g., Power BI), ensuring the main transactional database remains locked only for brief periods.

## Setup & Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd experiment_tracking
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the application:**
    ```bash
    streamlit run app.py
    ```

## Documentation
- **[Usage Guide](EXAMPLE_USAGE.md):** Detailed examples of how to use the system.
- **[Migration Testing](MIGRATION_TESTING_README.md):** Guidelines for testing database migrations.
- **[Dashboards](power_bi_elemental_analysis_dashboard.md):** Documentation for connected Power BI dashboards.
