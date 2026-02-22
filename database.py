"""
Database connection and session management
Using SQLite for portability
"""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Create data directory if it doesn't exist
DATA_DIR = Path("/workspace/doc_copilot/data")
DATA_DIR.mkdir(exist_ok=True)

# SQLite database path
DB_PATH = DATA_DIR / "doc_copilot.db"

# Create SQLite engine
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite
    poolclass=StaticPool,
    echo=False  # Set to True for SQL debugging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    Dependency for FastAPI routes
    Usage: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database
    Create all tables
    """
    from models import Base
    Base.metadata.create_all(bind=engine)
    print(f"✅ Database initialized at {DB_PATH}")