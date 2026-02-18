from celery import Celery
import os
from src.transcribe import transcribe_with_whisper
from src.utils import clean_to_csv
from src.models import SessionLocal, Transcription
import structlog

logger = structlog.get_logger()
app = Celery("avtranscribe", broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"))

@app.task
def transcribe_task(file_path: str, language: str, format: str, task_id: str):
    db = SessionLocal()
    trans = db.query(Transcription).filter(Transcription.id == task_id).first()
    trans.status = "processing"
    db.commit()
    
    try:
        text = transcribe_with_whisper(file_path, language, format)
        csv_path = clean_to_csv(text, task_id)
        trans.text = text
        trans.csv_path = csv_path
        trans.status = "done"
        logger.info("Transcription complete", task_id=task_id)
    except Exception as e:
        trans.status = f"error: {str(e)}"
        logger.error("Transcription failed", exc_info=e)
    finally:
        db.commit()
        db.close()
        if os.path.exists(file_path):
            os.remove(file_path)
