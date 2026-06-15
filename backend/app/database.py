from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings
import logging

logger = logging.getLogger(__name__)


def _make_engine():
    """Build the engine. SQLite (tests) skips Postgres-only pool args."""
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        return create_engine(
            url,
            echo=settings.SQLALCHEMY_ECHO,
            connect_args={"check_same_thread": False},
        )
    return create_engine(
        url,
        echo=settings.SQLALCHEMY_ECHO,
        pool_size=20,
        max_overflow=40,
        pool_recycle=3600,
        pool_pre_ping=True,
    )


# Database engine
engine = _make_engine()

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base for models
Base = declarative_base()

def get_db():
    """Dependency for getting DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database - create all tables"""
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")
