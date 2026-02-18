import pandas as pd
import os
from fastapi import UploadFile

def validate_file(file: UploadFile) -> bool:
    allowed_types = ["audio/mpeg", "audio/wav", "video/mp4", "video/avi", "video/quicktime"]
    max_size = 100 * 1024 * 1024
    return file.content_type in allowed_types and (file.size or 0) <= max_size

def clean_to_csv(segments: list, task_id: str) -> str:
    """
    Converts Whisper segments to a CSV file.
    
    Args:
        segments: List of segment dictionaries from Whisper result.
        task_id: Unique task identifier for naming the file.
        
    Returns:
        Path to the generated CSV file.
    """
    data = []
    for seg in segments:
        data.append({
            "start": seg.get("start"),
            "end": seg.get("end"),
            "text": seg.get("text", "").strip()
        })
    
    df = pd.DataFrame(data)
    csv_path = f"/tmp/{task_id}.csv"
    df.to_csv(csv_path, index=False)
    return csv_path
