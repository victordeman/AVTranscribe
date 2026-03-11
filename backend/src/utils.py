import csv
import os
import smtplib
import ssl
import structlog
from email.message import EmailMessage
from fastapi import UploadFile

logger = structlog.get_logger()

def send_error_email(task_id: str, error_message: str):
    """
    Sends an error alert email when a transcription task fails.
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT", "587")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    to_email = os.getenv("ALERT_EMAIL_TO")

    if not all([smtp_host, smtp_user, smtp_password, to_email]):
        logger.warning("SMTP configuration incomplete. Skipping error email.", task_id=task_id)
        return

    msg = EmailMessage()
    msg.set_content(f"Transcription task {task_id} failed.\n\nError: {error_message}")
    msg["Subject"] = f"AVTranscribe Alert: Task Failure ({task_id})"
    msg["From"] = smtp_user
    msg["To"] = to_email

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        logger.info("Error alert email sent", task_id=task_id, recipient=to_email)
    except Exception as e:
        logger.error("Failed to send error alert email", task_id=task_id, error=str(e))

def validate_file(file: UploadFile) -> bool:
    """
    Validates the uploaded file based on MIME type, file extension, and size.
    
    Args:
        file: The uploaded file object.
        
    Returns:
        True if the file is valid, False otherwise.
    """
    allowed_types = ["audio/mpeg", "audio/wav", "video/mp4", "video/avi", "video/quicktime"]
    allowed_extensions = {".mp3", ".wav", ".mp4", ".avi", ".mov"}
    max_size = 100 * 1024 * 1024
    
    # Check MIME type
    is_valid_type = file.content_type in allowed_types
    
    # Fallback to extension check if MIME type is generic or missing
    if not is_valid_type:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in allowed_extensions:
            return False
            
    # Check size if available
    if file.size is not None and file.size > max_size:
        return False
        
    return True

def clean_to_csv(segments: list, task_id: str) -> str:
    """
    Converts Whisper segments to a CSV file.
    
    Args:
        segments: List of segment dictionaries from Whisper result.
        task_id: Unique task identifier for naming the file.
        
    Returns:
        Path to the generated CSV file.
    """
    csv_path = f"/tmp/{task_id}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["start", "end", "text"])
        writer.writeheader()
        for seg in segments:
            writer.writerow({
                "start": seg.get("start"),
                "end": seg.get("end"),
                "text": seg.get("text", "").strip()
            })
    return csv_path

def save_text(text: str, task_id: str) -> str:
    """
    Saves transcription text to a plain text file.
    
    Args:
        text: The transcription text.
        task_id: Unique task identifier for naming the file.
        
    Returns:
        Path to the generated text file.
    """
    txt_path = f"/tmp/{task_id}.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text or "")
    return txt_path

def format_timestamp(seconds: float) -> str:
    """
    Formats seconds into [HH:MM:SS.mmm] format.
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"[{hours:02d}:{minutes:02d}:{secs:06.3f}]"

def save_timestamped_text(segments: list, task_id: str) -> str:
    """
    Saves transcription text with timestamps to a plain text file.
    
    Args:
        segments: List of segment dictionaries from Whisper result.
        task_id: Unique task identifier for naming the file.
        
    Returns:
        Path to the generated timestamped text file.
    """
    txt_path = f"/tmp/{task_id}_timestamps.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        for seg in segments:
            start = format_timestamp(seg.get("start", 0.0))
            end = format_timestamp(seg.get("end", 0.0))
            text = seg.get("text", "").strip()
            f.write(f"{start} --> {end}  {text}\n")
    return txt_path
