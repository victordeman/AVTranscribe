from sqlalchemy import Column, String, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from contextlib import contextmanager

Base = declarative_base()

# DB Setup
DB_URL = os.getenv("DB_URL", "sqlite:///transcriptions.db")
ENGINE = create_engine(DB_URL, connect_args={"check_same_thread": False} if "sqlite" in DB_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)

@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

class Transcription(Base):
    __tablename__ = "transcriptions"
    id = Column(String, primary_key=True, index=True)
    status = Column(String, default="queued")
    text = Column(String)
    csv_path = Column(String)
