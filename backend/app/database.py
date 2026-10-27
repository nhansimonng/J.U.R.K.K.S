from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from fastapi import HTTPException

from app.config import DATABASE_URL

# SQLAlchemy needs the driver name in the URL
url = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1) if DATABASE_URL else None

engine = create_engine(url, pool_pre_ping=True) if url else None
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


def get_db():
    """Give each request its own database session, then close it."""
    if engine is None:
        raise HTTPException(503, "Database is not configured")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
