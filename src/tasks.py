from celery import Celery
import os
from src.transcribe import transcribe_with_whisper
from src.utils import clean_to_csv
from src.models import session_scope, Transcription
import structlog

logger = structlog.get_logger()
app = Celery("avtranscribe", broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"))

@app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def transcribe_task(self, file_path: str, language: str, format: str, task_id: str) -> None:
    """
    Celery task to handle the end-to-end transcription process.

    Args:
        self: The task instance (due to bind=True).
        file_path: Local path to the media file.
        language: Language code or 'auto'.
        format: Format hint ('audio', 'video', or 'auto').
        task_id: Unique ID for the transcription record in the DB.
    """
    logger.info("Task started", task_id=task_id, file_path=file_path, retry=self.request.retries)

    with session_scope() as db:
        trans = db.query(Transcription).filter(Transcription.id == task_id).first()
        if not trans:
            logger.error("Transcription record not found", task_id=task_id)
            if os.path.exists(file_path):
                os.remove(file_path)
            return

        trans.status = "processing"
        db.add(trans)
    
    try:
        text = transcribe_with_whisper(file_path, language, format)
        csv_path = clean_to_csv(text, task_id)

        with session_scope() as db:
            trans = db.query(Transcription).filter(Transcription.id == task_id).first()
            if trans:
                trans.text = text
                trans.csv_path = csv_path
                trans.status = "done"
                db.add(trans)

        logger.info("Transcription complete and record updated", task_id=task_id)

        # Success: clean up
        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        logger.error("Transcription failed", task_id=task_id, error=str(e), retry=self.request.retries)

        with session_scope() as db:
            trans = db.query(Transcription).filter(Transcription.id == task_id).first()
            if trans:
                if self.request.retries >= self.max_retries:
                    trans.status = f"failed after {self.max_retries} retries: {str(e)}"
                    # Final failure: clean up
                    if os.path.exists(file_path):
                        os.remove(file_path)
                else:
                    trans.status = f"retrying (attempt {self.request.retries + 1})..."
                db.add(trans)

        raise e  # Re-raise to trigger Celery retry
