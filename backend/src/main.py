from fastapi import FastAPI, UploadFile, Form, Request, HTTPException, Depends, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from .models import Base, Transcription, User, SessionLocal, engine, session_scope
from .transcribe import transcribe_with_whisper
from .utils import validate_file, save_text, clean_to_csv, save_timestamped_text, send_error_email
from .auth import authenticate_user, create_access_token, get_current_user, get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES
from datetime import timedelta
import uuid
import os
import shutil
import structlog

logger = structlog.get_logger()

# Use absolute paths for Vercel deployment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(os.path.dirname(BASE_DIR), "static")
FRONTEND_DIST_DIR = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), "frontend", "dist")

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# Security: Enforce HTTPS if configured
if os.getenv("ENFORCE_HTTPS", "").lower() == "true":
    app.add_middleware(HTTPSRedirectMiddleware)

# CORS configuration
allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
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

# Serve React assets if dist exists
if os.path.exists(os.path.join(FRONTEND_DIST_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST_DIR, "assets")), name="assets")

# PWA Support: Serve manifest, service worker, and icons from root
@app.get("/manifest.json")
async def get_manifest():
    fe_manifest = os.path.join(FRONTEND_DIST_DIR, "manifest.json")
    if os.path.exists(fe_manifest):
        return FileResponse(fe_manifest)
    return FileResponse(os.path.join(STATIC_DIR, "manifest.json"))

@app.get("/sw.js")
async def get_sw():
    fe_sw = os.path.join(FRONTEND_DIST_DIR, "sw.js")
    if os.path.exists(fe_sw):
        return FileResponse(fe_sw, media_type="application/javascript")
    return FileResponse(os.path.join(STATIC_DIR, "sw.js"), media_type="application/javascript")

@app.get("/icon.svg")
async def get_icon():
    fe_icon = os.path.join(FRONTEND_DIST_DIR, "icon.svg")
    if os.path.exists(fe_icon):
        return FileResponse(fe_icon)
    return FileResponse(os.path.join(STATIC_DIR, "icon.svg"))

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

def run_transcription_sync(file_path: str, language: str, format: str, task_id: str, diarize: bool = False):
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

        result = transcribe_with_whisper(file_path, language=language, on_segment=on_segment, diarize=diarize)

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
        send_error_email(task_id, str(e))
        with session_scope() as db:
            trans = db.query(Transcription).filter(Transcription.id == task_id).first()
            if trans:
                trans.status = "failed"
                trans.error_message = str(e)
        if os.path.exists(file_path):
            os.remove(file_path)

@app.post("/signup")
async def signup(username: str = Form(...), password: str = Form(...), db = Depends(get_db)):
    if len(username) < 3 or len(username) > 50:
        raise HTTPException(status_code=400, detail="Username must be between 3 and 50 characters")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")
    if len(password) > 72:
        raise HTTPException(status_code=400, detail="Password must be at most 72 characters long")

    user = db.query(User).filter(User.username == username).first()
    if user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = get_password_hash(password)
    new_user = User(username=username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    return {"message": "User created successfully"}

@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Try to serve React app first if built
    react_index = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(react_index):
        return FileResponse(react_index)
    
    # Fallback to HTMX version
    return templates.TemplateResponse(request, "index.html")

@app.post("/transcribe")
@limiter.limit(os.getenv("RATE_LIMIT", "10/minute"))
async def transcribe(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile,
    language: str = Form("auto"),
    format: str = Form("auto"),
    diarize: bool = Form(False),
    db = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Input validation
    allowed_languages = {"auto", "en", "es", "fr", "de", "it", "pt", "nl", "ja", "ko", "zh"}
    allowed_formats = {"auto", "text", "csv", "text_timestamps"}

    if language not in allowed_languages and len(language) != 2:
        raise HTTPException(status_code=400, detail="Invalid language code")

    if format not in allowed_formats:
        raise HTTPException(status_code=400, detail="Invalid format")

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
        language=language,
        diarize=diarize
    )
    db.add(trans)
    db.commit()
    
    # Decide between Celery and BackgroundTasks
    use_celery = os.getenv("REDIS_URL") is not None and os.getenv("VERCEL") is None
    if use_celery:
        from .tasks import transcribe_task
        transcribe_task.delay(temp_path, language, format, task_id, diarize)
    else:
        logger.info("Using BackgroundTasks (Serverless Mode)", task_id=task_id)
        background_tasks.add_task(run_transcription_sync, temp_path, language, format, task_id, diarize)
    
    if "application/json" in request.headers.get("Accept", ""):
        return JSONResponse({"task_id": task_id, "status": "queued", "progress": 0})

    return templates.TemplateResponse(
        request, 
        "status_partial.html", 
        {"task_id": task_id, "status": "queued", "progress": 0}
    )

@app.get("/status/{task_id}")
async def get_status(request: Request, task_id: uuid.UUID, db = Depends(get_db)):
    task_id_str = str(task_id)
    trans = db.query(Transcription).filter(Transcription.id == task_id_str).first()
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
async def download(task_id: uuid.UUID, fmt: str, db = Depends(get_db)):
    task_id_str = str(task_id)
    allowed_fmts = {"text", "csv", "text_timestamps"}
    if fmt not in allowed_fmts:
        raise HTTPException(status_code=400, detail="Invalid format: text, csv or text_timestamps")

    trans = db.query(Transcription).filter(Transcription.id == task_id_str).first()
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
            # Note: This is a heavy fallback, usually the file should exist.
            # However, for simplicity if it's missing we just return 404 for now
            # as re-transcribing here is not feasible without the original file.
            raise HTTPException(status_code=404, detail="Timestamped text file not found")
        return FileResponse(trans.text_timestamps_path, filename="transcription_timestamps.txt")
    
    raise HTTPException(status_code=400, detail="Invalid format: text, csv or text_timestamps")
