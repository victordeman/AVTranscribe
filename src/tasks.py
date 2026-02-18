from celery import Celery
import os
from src.transcribe import transcribe_with_whisper
from src.utils import clean_to_csv
from src.models import session_scope, Transcription
import structlog

logger = structlog.get_logger()
app = Celery("avtranscribe", broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"))

@app.task(bind=True, max_retries=3)
def transcribe_task(self, file_path: str, language: str, format: str, task_id: str):
    """
    Celery task for transcribing media files with automated retries.
    """
    try:
        # Update status to processing
        with session_scope() as db:
            trans = db.query(Transcription).filter(Transcription.id == task_id).first()
            if not trans:
                logger.error("Transcription record not found", task_id=task_id)
                return
            trans.status = "processing"

        logger.info("Starting transcription task", task_id=task_id, file=file_path)
        
        # Execute transcription
        result = transcribe_with_whisper(file_path, language=language)
        
        text = result.get("text", "").strip()
        segments = result.get("segments", [])
        csv_path = clean_to_csv(segments, task_id)
        
        # Update record with results
        with session_scope() as db:
            trans = db.query(Transcription).filter(Transcription.id == task_id).first()
            if trans:
                trans.text = text
                trans.csv_path = csv_path
                trans.status = "done"
        
        logger.info("Transcription complete", task_id=task_id)
        
        # Cleanup input file on success
        if os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        logger.error("Transcription task failed", task_id=task_id, error=str(e))
        
        # Handle retries
        if self.request.retries < self.max_retries:
            with session_scope() as db:
                trans = db.query(Transcription).filter(Transcription.id == task_id).first()
                if trans:
                    trans.status = f"retrying ({self.request.retries + 1}/{self.max_retries})"
            
            # Exponential backoff: 60, 120, 240 seconds
            retry_delay = 60 * (2 ** self.request.retries)
            raise self.retry(exc=e, countdown=retry_delay)
        else:
            # Final failure
            with session_scope() as db:
                trans = db.query(Transcription).filter(Transcription.id == task_id).first()
                if trans:
                    trans.status = f"failed after {self.max_retries} retries: {str(e)}"
            
            # Cleanup input file on final failure
            if os.path.exists(file_path):
                os.remove(file_path)
            raise e
