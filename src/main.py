from fastapi import FastAPI, UploadFile, Form, Request, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from src.models import Base, Transcription, SessionLocal, engine
from src.tasks import transcribe_task
from src.utils import validate_file
import uuid
import os
import shutil
import structlog

logger = structlog.get_logger()

app = FastAPI()
templates = Jinja2Templates(directory="src/templates")

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
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.post("/transcribe")
@limiter.limit(os.getenv("RATE_LIMIT", "10/minute"))
async def transcribe(
    request: Request,
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
    trans = Transcription(id=task_id, status="queued")
    db.add(trans)
    db.commit()
    
    transcribe_task.delay(temp_path, language, format, task_id)
    return {"task_id": task_id, "status": "queued"}

@app.get("/status/{task_id}")
async def get_status(task_id: str, db = Depends(get_db)):
    trans = db.query(Transcription).filter(Transcription.id == task_id).first()
    if not trans:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": trans.status}

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
            with open(file_path, "w") as f:
                f.write(trans.text or "")
        return FileResponse(file_path, filename="transcription.txt")
    elif fmt == "csv":
        if not trans.csv_path or not os.path.exists(trans.csv_path):
             raise HTTPException(status_code=404, detail="CSV file not found")
        return FileResponse(trans.csv_path, filename="transcription.csv")
    
    raise HTTPException(status_code=400, detail="Invalid format: text or csv")
