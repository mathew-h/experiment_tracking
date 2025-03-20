# Experiment Tracker

A web application for tracking experiments using Streamlit and SQLAlchemy.

## Setup

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure the database:
   - For PostgreSQL:
     ```bash
     DATABASE_URL=postgresql://user:password@localhost:5432/dbname
     ```
   - For SQLite (development):
     ```bash
     DATABASE_URL=sqlite:///experiments.db
     ```

4. Initialize the database:
```bash
python init_db.py
```
This will:
- Check the database connection
- Ask for confirmation before resetting the database
- Create all necessary tables

5. Run the application:
```bash
streamlit run app.py
```

## Features

- Track experiments and their results
- Store experiment metadata and parameters
- Visualize experiment outcomes
- (More features to be added)

## Development

The application uses:
- Streamlit for the frontend
- SQLAlchemy for database management
- SQLite for local development (can be configured to use PostgreSQL)

## Database Structure

The application uses the following tables:
- `experiments`: Main experiment metadata
- `experimental_conditions`: Experiment parameters
- `results`: Analysis results
- `experiment_notes`: Lab notes and observations
- `modifications_log`: Audit trail for changes 