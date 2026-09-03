from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os

# Default to local postgres if not provided, but fallback to sqlite if running tests
if os.getenv("TESTING", "False").lower() in ("true", "1", "t"):
    SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
    connect_args = {"check_same_thread": False}
else:
    SQLALCHEMY_DATABASE_URL = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres_admin:REPLACE_WITH_SECURE_PASSWORD_IN_SECRETS_MANAGER@localhost:5432/siih2026"
    )
    connect_args = {}

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
