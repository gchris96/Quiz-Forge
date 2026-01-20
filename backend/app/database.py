# SQLAlchemy engine/session setup and DB dependency.
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.env import load_environment

load_environment()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/quiz_forge",
)

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Provide a SQLAlchemy session for request-scoped usage.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
