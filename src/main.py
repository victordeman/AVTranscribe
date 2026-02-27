from fastapi import FastAPI, UploadFile, Form, Request, HTTPException, Depends, status
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from src.models import Base, Transcription, SessionLocal, engine
from src.tasks import transcribe_task
from src.utils import validate_file, save_text
from prometheus_fastapi_instrumentator import Instrumentator
import uuid
import os
import shutil
import structlog
import secrets

logger = structlog.get_logger()

app = FastAPI()

# Prometheus
Instrumentator().instrument(app).expose(app)

templates = Jinja2Templates(directory="src/templates")

# DB Setup
Base.metadata.create_all(bind=engine)

# Authentication
security = HTTPBasic(auto_error=False)

def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Basic"},
        )
    correct_username = os.getenv("AUTH_USERNAME")
    correct_password = os.getenv("AUTH_PASSWORD")

    if not correct_username or not correct_password:
        return None # Auth disabled

    is_correct_username = secrets.compare_digest(credentials.username, correct_username)
    is_correct_password = secrets.compare_digest(credentials.password, correct_password)

    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

def optional_auth(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = os.getenv("AUTH_USERNAME")
    correct_password = os.getenv("AUTH_PASSWORD")

    if not correct_username or not correct_password:
        return None

    return get_current_user(credentials)

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
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user = Depends(optional_auth)):
    return templates.TemplateResponse(request, "index.html")

@app.post("/transcribe")
@limiter.limit(os.getenv("RATE_LIMIT", "10/minute"))
async def transcribe(
    request: Request,
    file: UploadFile,
    language: str = Form("auto"),
    format: str = Form("auto"),
    db = Depends(get_db),
    user = Depends(optional_auth)
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
    
    transcribe_task.delay(temp_path, language, format, task_id)
    
    return templates.TemplateResponse(
        request, 
        "status_partial.html", 
        {"task_id": task_id, "status": "queued", "progress": 0}
    )

@app.get("/status/{task_id}", response_class=HTMLResponse)
async def get_status(request: Request, task_id: str, db = Depends(get_db), user = Depends(optional_auth)):
    trans = db.query(Transcription).filter(Transcription.id == task_id).first()
    if not trans:
        raise HTTPException(status_code=404, detail="Task not found")
    
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
async def download(task_id: str, fmt: str, db = Depends(get_db), user = Depends(optional_auth)):
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
    
    raise HTTPException(status_code=400, detail="Invalid format: text or csv")
