# Experiment Tracker

A comprehensive web application for tracking and managing experiments, built with Streamlit, SQLAlchemy, and Firebase authentication.

## Project Structure

```
experiment_tracking/
├── app.py                 # Main Streamlit application
├── database/             # Database models and configuration
├── frontend/             # Frontend components and pages
├── backend/              # Backend services and utilities
├── auth/                 # Authentication and user management
├── scripts/              # Utility scripts
├── tests/                # Test suite
├── config/               # Configuration files
├── utils/                # Utility functions
├── data/                 # Data storage
└── uploads/              # File upload directory
```

## Setup

1. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
Create a `.env` file in the root directory with:
```bash
# Database Configuration
DATABASE_URL=sqlite:///experiments.db  # For development
# DATABASE_URL=postgresql://user:password@localhost:5432/dbname  # For production

# Firebase Configuration (for authentication)
FIREBASE_API_KEY=your_api_key
FIREBASE_AUTH_DOMAIN=your_auth_domain
FIREBASE_PROJECT_ID=your_project_id
FIREBASE_STORAGE_BUCKET=your_storage_bucket
FIREBASE_MESSAGING_SENDER_ID=your_messaging_sender_id
FIREBASE_APP_ID=your_app_id
```

4. Initialize the database:
```bash
# Using Alembic for database migrations
alembic upgrade head
```

5. Run the application:
```bash
streamlit run app.py
```

## Features

- **Experiment Management**
  - Track experiments and their results
  - Store experiment metadata and parameters
  - Record experimental conditions
  - Manage sample information

- **Data Analysis**
  - NMR results analysis
  - Scalar results tracking
  - External analysis integration
  - PXRF readings management

- **User Management**
  - Firebase authentication
  - Role-based access control
  - User approval workflow
  - Custom user claims

- **File Management**
  - Upload and store experiment files
  - Manage sample photos
  - Track analysis files
  - External analysis documentation

## Development

The application uses:
- **Frontend**: Streamlit
- **Backend**: Python with SQLAlchemy
- **Database**: SQLite (development) / PostgreSQL (production)
- **Authentication**: Firebase
- **File Storage**: Local storage / Cloud storage options

## Database Structure

The application uses the following main tables:
- `experiments`: Main experiment metadata
- `experimental_conditions`: Experiment parameters
- `experimental_results`: Analysis results
- `nmr_results`: NMR-specific data
- `scalar_results`: Scalar measurements
- `sample_info`: Sample information
- `external_analyses`: External analysis data
- `pxrf_readings`: PXRF analysis data
- `experiment_notes`: Lab notes and observations
- `modifications_log`: Audit trail for changes

## User Management

The application includes a user management system accessible via:
```bash
python run.py
```

Available commands:
- `create`: Create new users
- `list`: List all users
- `delete`: Delete users
- `update`: Update user information
- `pending`: List pending user requests
- `approve`: Approve user requests
- `reject`: Reject user requests
- `set-claims`: Set user roles and permissions 