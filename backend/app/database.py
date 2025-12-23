"""데이터베이스 설정 및 세션 관리."""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLite database URL for development
DATABASE_URL = "sqlite:///./trpg_world.db"

# Create SQLAlchemy engine
# check_same_thread=False is needed for SQLite to work with FastAPI
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create SessionLocal class for database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for declarative models
Base = declarative_base()


def get_db():
    """
    Dependency function to get database session.
    Yields a database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
