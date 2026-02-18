import os
from sqlalchemy import Column, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DB_URL = os.getenv("DB_URL", "sqlite:///transcriptions.db")
engine = create_engine(
    DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Transcription(Base):
    __tablename__ = "transcriptions"
    id = Column(String, primary_key=True, index=True)
    status = Column(String, default="queued")
    text = Column(String, nullable=True)
    csv_path = Column(String, nullable=True)
