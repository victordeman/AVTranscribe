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
    try:
        trans = db.query(Transcription).filter(Transcription.id == task_id).first()
        if not trans:
            logger.error("Task not found in database", task_id=task_id)
            return

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
            db.rollback()
            trans.status = f"error: {str(e)}"
            logger.error("Transcription failed", task_id=task_id, error=str(e))
        finally:
            db.commit()
    finally:
        db.close()
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning("Failed to remove temporary file", path=file_path, error=str(e))
