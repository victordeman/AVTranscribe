import csv
import os
from fastapi import UploadFile

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
