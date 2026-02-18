import pandas as pd
import os
from fastapi import UploadFile

def validate_file(file: UploadFile) -> bool:
    allowed_types = ["audio/mpeg", "audio/wav", "video/mp4", "video/avi", "video/quicktime"]
    max_size = 100 * 1024 * 1024
    return file.content_type in allowed_types and (file.size or 0) <= max_size

def clean_to_csv(text: str, task_id: str) -> str:
    # Simple ETL: Split lines, add dummy timestamps if needed
    lines = text.split("\n")
    df = pd.DataFrame({"timestamp": ["00:00"] * len(lines), "text": lines})  # Enhance with real timestamps if Whisper provides
    csv_path = f"/tmp/{task_id}.csv"
    df.to_csv(csv_path, index=False)
    return csv_path
