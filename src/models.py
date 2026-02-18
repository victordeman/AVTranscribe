from sqlalchemy import Column, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

Base = declarative_base()

# DB Setup
ENGINE = create_engine(os.getenv("DB_URL", "sqlite:///transcriptions.db"))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)

class Transcription(Base):
    __tablename__ = "transcriptions"
    id = Column(String, primary_key=True, index=True)
    status = Column(String, default="queued")
    text = Column(String)
    csv_path = Column(String)
