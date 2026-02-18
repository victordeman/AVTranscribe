from fastapi import FastAPI, UploadFile, Form, Request, HTTPException, Depends, Header
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from typing import Optional
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from src.models import Base, Transcription, SessionLocal, ENGINE
from src.tasks import transcribe_task
from src.utils import validate_file
import uuid
import os
import structlog

logger = structlog.get_logger()

app = FastAPI()
templates = Jinja2Templates(directory="src/templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(HTTPException, _rate_limit_exceeded_handler)

# DB Setup
Base.metadata.create_all(bind=ENGINE)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/transcribe")
@limiter.limit(os.getenv("RATE_LIMIT", "10/minute"))
async def transcribe(
    request: Request,
    file: UploadFile,
    language: str = Form("auto"),
    format: str = Form("auto"),
    db = Depends(get_db),
    hx_request: Optional[str] = Header(None)
):
    if not validate_file(file):
        logger.error("Invalid file upload", filename=file.filename)
        raise HTTPException(400, "Invalid file: Check type/size (max 100MB)")
    temp_path = f"/tmp/{uuid.uuid4()}_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    
    task_id = str(uuid.uuid4())
    trans = Transcription(id=task_id, status="queued")
    db.add(trans)
    db.commit()
    
    transcribe_task.delay(temp_path, language, format, task_id)

    if hx_request:
        return templates.TemplateResponse("status_partial.html", {
            "request": request,
            "task_id": task_id,
            "status": "queued"
        })
    return {"task_id": task_id, "status": "queued"}

@app.get("/status/{task_id}")
async def get_status(
    request: Request,
    task_id: str,
    db = Depends(get_db),
    hx_request: Optional[str] = Header(None)
):
    trans = db.query(Transcription).filter(Transcription.id == task_id).first()
    if not trans:
        raise HTTPException(404, "Task not found")

    if hx_request:
        return templates.TemplateResponse("status_partial.html", {
            "request": request,
            "task_id": task_id,
            "status": trans.status
        })
    return {"status": trans.status}

@app.get("/download/{task_id}/{fmt}")
async def download(task_id: str, fmt: str, db = Depends(get_db)):
    trans = db.query(Transcription).filter(Transcription.id == task_id).first()
    if not trans or trans.status != "done":
        raise HTTPException(400, "Task not complete")
    if fmt == "text":
        file_path = f"/tmp/{task_id}.txt"
        with open(file_path, "w") as f:
            f.write(trans.text)
        return FileResponse(file_path, filename="transcription.txt")
    elif fmt == "csv":
        return FileResponse(trans.csv_path, filename="transcription.csv")
    raise HTTPException(400, "Invalid format: text or csv")
