from sqlalchemy import String, create_engine, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
import os
from contextlib import contextmanager
from datetime import datetime, UTC

class Base(DeclarativeBase):
    pass

# DB Setup
DB_URL = os.getenv("DB_URL", "sqlite:///transcriptions.db")
# Add sqlite-specific settings if needed, and ensure pool for in-memory
engine_args = {}
if "sqlite" in DB_URL:
    engine_args["connect_args"] = {"check_same_thread": False}
    if ":memory:" in DB_URL:
         from sqlalchemy.pool import StaticPool
         engine_args["poolclass"] = StaticPool

engine = create_engine(DB_URL, **engine_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)

class Transcription(Base):
    __tablename__ = "transcriptions"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String, default="queued")
    text: Mapped[str | None] = mapped_column(String, nullable=True)
    csv_path: Mapped[str | None] = mapped_column(String, nullable=True)
    text_timestamps_path: Mapped[str | None] = mapped_column(String, nullable=True)
    filename: Mapped[str | None] = mapped_column(String, nullable=True)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    diarize: Mapped[bool] = mapped_column(default=False)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    progress: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
