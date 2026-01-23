from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import sys
import os

# Add parent directory to path for config import
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import DATABASE_URL, DB_CONNECT_ARGS

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL, connect_args=DB_CONNECT_ARGS)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base
Base = declarative_base()

# Import to register listeners. This must be done after Base is defined to avoid circular imports.
from . import event_listeners

def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 