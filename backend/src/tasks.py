from celery import Celery
import os
import time
from src.transcribe import transcribe_with_whisper
from src.utils import clean_to_csv
from src.models import session_scope, Transcription
import structlog

logger = structlog.get_logger()
app = Celery("avtranscribe", broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"))

# Configure Celery Beat for periodic cleanup
app.conf.beat_schedule = {
    'cleanup-temp-files-every-hour': {
        'task': 'src.tasks.cleanup_temp_files',
        'schedule': 3600.0,
    },
}

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
        progress_count = len(segments)
        csv_path = clean_to_csv(segments, task_id)
        
        # Update record with results
        with session_scope() as db:
            trans = db.query(Transcription).filter(Transcription.id == task_id).first()
            if trans:
                trans.text = text
                trans.csv_path = csv_path
                trans.progress = progress_count
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
                    trans.status = "failed"
                    trans.error_message = f"Failed after {self.max_retries} retries: {str(e)}"
            
            # Cleanup input file on final failure
            if os.path.exists(file_path):
                os.remove(file_path)
            raise e

@app.task
def cleanup_temp_files():
    """
    Cleans up files in /tmp that are older than 24 hours and match AVTranscribe patterns.
    """
    logger.info("Starting periodic cleanup of temp files")
    tmp_dir = "/tmp"
    now = time.time()
    cutoff = now - (24 * 3600)
    
    count = 0
    for filename in os.listdir(tmp_dir):
        # Match files that have a UUID prefix (typical for our app)
        # Patterns: {uuid}_{filename} or {uuid}.txt / {uuid}.csv
        is_app_file = False
        if any(filename.endswith(ext) for ext in [".txt", ".csv", ".mp3", ".wav", ".mp4", ".avi", ".mov"]):
             # Check for UUID-like prefix (36 chars for UUID)
             if len(filename) >= 36:
                 is_app_file = True

        if is_app_file:
            file_path = os.path.join(tmp_dir, filename)
            try:
                if os.path.getmtime(file_path) < cutoff:
                    os.remove(file_path)
                    count += 1
            except Exception as e:
                logger.warning(f"Failed to delete {file_path}", error=str(e))
    
    logger.info(f"Cleanup finished. Deleted {count} files.")
