from sqlalchemy import Column, String, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

Base = declarative_base()

# DB Setup
DB_URL = os.getenv("DB_URL", "sqlite:///transcriptions.db")
ENGINE = create_engine(DB_URL, connect_args={"check_same_thread": False} if "sqlite" in DB_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)

class Transcription(Base):
    __tablename__ = "transcriptions"
    id = Column(String, primary_key=True, index=True)
    status = Column(String, default="queued")
    text = Column(String)
    csv_path = Column(String)
