from fastapi import FastAPI, UploadFile, Form, Request, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from src.models import Base, Transcription, SessionLocal, engine, session_scope
from src.transcribe import transcribe_with_whisper
from src.utils import validate_file, save_text, clean_to_csv, save_timestamped_text
import uuid
import os
import shutil
import structlog

logger = structlog.get_logger()

# Use absolute paths for Vercel deployment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(os.path.dirname(BASE_DIR), "static")

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB Setup
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Static files
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def update_progress_sync(task_id: str):
    """
    Synchronous helper to increment progress.
    """
    try:
        with session_scope() as db:
            trans = db.query(Transcription).filter(Transcription.id == task_id).first()
            if trans:
                trans.progress += 1
    except Exception as e:
        logger.error("Failed to update task progress", task_id=task_id, error=str(e))

def run_transcription_sync(file_path: str, language: str, format: str, task_id: str):
    """
    Synchronous transcription helper for BackgroundTasks (used in serverless mode).
    """
    try:
        with session_scope() as db:
            trans = db.query(Transcription).filter(Transcription.id == task_id).first()
            if trans:
                trans.status = "processing"
                trans.progress = 0

        def on_segment():
            update_progress_sync(task_id)

        result = transcribe_with_whisper(file_path, language=language, on_segment=on_segment)

        text = result.get("text", "").strip()
        segments = result.get("segments", [])
        detected_lang = result.get("language", language)
        csv_path = clean_to_csv(segments, task_id)
        text_timestamps_path = save_timestamped_text(segments, task_id)

        with session_scope() as db:
            trans = db.query(Transcription).filter(Transcription.id == task_id).first()
            if trans:
                trans.text = text
                trans.csv_path = csv_path
                trans.text_timestamps_path = text_timestamps_path
                trans.language = detected_lang
                trans.progress = len(segments)
                trans.status = "done"

        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        logger.error("Background transcription failed", task_id=task_id, error=str(e))
        with session_scope() as db:
            trans = db.query(Transcription).filter(Transcription.id == task_id).first()
            if trans:
                trans.status = "failed"
                trans.error_message = str(e)
        if os.path.exists(file_path):
            os.remove(file_path)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.post("/transcribe")
@limiter.limit(os.getenv("RATE_LIMIT", "10/minute"))
async def transcribe(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile,
    language: str = Form("auto"),
    format: str = Form("auto"),
    db = Depends(get_db)
):
    if not validate_file(file):
        logger.error("Invalid file upload", filename=file.filename or "unknown")
        raise HTTPException(status_code=400, detail="Invalid file: Check type/size (max 100MB)")
    
    safe_filename = os.path.basename(file.filename or "uploaded_file")
    temp_path = f"/tmp/{uuid.uuid4()}_{safe_filename}"
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error("Failed to save uploaded file", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")
    
    task_id = str(uuid.uuid4())
    trans = Transcription(
        id=task_id, 
        status="queued",
        filename=safe_filename,
        language=language
    )
    db.add(trans)
    db.commit()
    
    # Decide between Celery and BackgroundTasks
    use_celery = os.getenv("REDIS_URL") is not None and os.getenv("VERCEL") is None
    if use_celery:
        from src.tasks import transcribe_task
        transcribe_task.delay(temp_path, language, format, task_id)
    else:
        logger.info("Using BackgroundTasks (Serverless Mode)", task_id=task_id)
        background_tasks.add_task(run_transcription_sync, temp_path, language, format, task_id)
    
    if "application/json" in request.headers.get("Accept", ""):
        return JSONResponse({"task_id": task_id, "status": "queued", "progress": 0})

    return templates.TemplateResponse(
        request, 
        "status_partial.html", 
        {"task_id": task_id, "status": "queued", "progress": 0}
    )

@app.get("/status/{task_id}")
async def get_status(request: Request, task_id: str, db = Depends(get_db)):
    trans = db.query(Transcription).filter(Transcription.id == task_id).first()
    if not trans:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if "application/json" in request.headers.get("Accept", ""):
        return JSONResponse({
            "task_id": task_id,
            "status": trans.status,
            "progress": trans.progress,
            "error_message": trans.error_message
        })

    return templates.TemplateResponse(
        request, 
        "status_partial.html", 
        {
            "task_id": task_id, 
            "status": trans.status, 
            "progress": trans.progress,
            "error_message": trans.error_message
        }
    )

@app.get("/download/{task_id}/{fmt}")
async def download(task_id: str, fmt: str, db = Depends(get_db)):
    trans = db.query(Transcription).filter(Transcription.id == task_id).first()
    if not trans:
        raise HTTPException(status_code=404, detail="Task not found")
    if trans.status != "done":
        raise HTTPException(status_code=400, detail=f"Task not complete. Current status: {trans.status}")
    
    if fmt == "text":
        file_path = f"/tmp/{task_id}.txt"
        if not os.path.exists(file_path):
            file_path = save_text(trans.text or "", task_id)
        return FileResponse(file_path, filename="transcription.txt")
    elif fmt == "csv":
        if not trans.csv_path or not os.path.exists(trans.csv_path):
             raise HTTPException(status_code=404, detail="CSV file not found")
        return FileResponse(trans.csv_path, filename="transcription.csv")
    elif fmt == "text_timestamps":
        if not trans.text_timestamps_path or not os.path.exists(trans.text_timestamps_path):
            # Fallback generation if file missing
            from src.transcribe import transcribe_with_whisper
            # Note: This is a heavy fallback, usually the file should exist.
            # However, for simplicity if it's missing we just return 404 for now
            # as re-transcribing here is not feasible without the original file.
            raise HTTPException(status_code=404, detail="Timestamped text file not found")
        return FileResponse(trans.text_timestamps_path, filename="transcription_timestamps.txt")
    
    raise HTTPException(status_code=400, detail="Invalid format: text, csv or text_timestamps")
