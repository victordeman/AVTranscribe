import os
import pytest
from src.utils import validate_file, clean_to_csv, save_text, save_timestamped_text, format_timestamp
from fastapi import UploadFile
from io import BytesIO
from starlette.datastructures import Headers

def test_validate_file_valid_mime():
    file = UploadFile(
        file=BytesIO(b"test"), 
        filename="test.mp3", 
        headers=Headers({"content-type": "audio/mpeg"}),
        size=10 * 1024 * 1024
    )
    assert validate_file(file) is True

def test_validate_file_invalid_mime_valid_extension():
    file = UploadFile(
        file=BytesIO(b"test"), 
        filename="test.mp4", 
        headers=Headers({"content-type": "application/octet-stream"}),
        size=1024
    )
    assert validate_file(file) is True

def test_validate_file_invalid_mime_invalid_extension():
    file = UploadFile(
        file=BytesIO(b"test"), 
        filename="test.txt", 
        headers=Headers({"content-type": "application/octet-stream"}),
        size=1024
    )
    assert validate_file(file) is False

def test_validate_file_too_large():
    file = UploadFile(
        file=BytesIO(b"test"), 
        filename="test.mp3", 
        headers=Headers({"content-type": "audio/mpeg"}),
        size=200 * 1024 * 1024
    )
    assert validate_file(file) is False

def test_validate_file_no_size():
    file = UploadFile(
        file=BytesIO(b"test"), 
        filename="test.mp3", 
        headers=Headers({"content-type": "audio/mpeg"}),
        size=None
    )
    assert validate_file(file) is True

def test_clean_to_csv():
    segments = [
        {"start": 0.0, "end": 2.0, "text": "Hello world"},
        {"start": 2.0, "end": 4.0, "text": "This is a test"}
    ]
    task_id = "test_task_csv"
    csv_path = clean_to_csv(segments, task_id)
    
    assert os.path.exists(csv_path)
    assert csv_path == f"/tmp/{task_id}.csv"
    
    with open(csv_path, "r", newline="") as f:
        import csv
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["text"] == "Hello world"
        assert rows[1]["text"] == "This is a test"
    
    os.remove(csv_path)

def test_save_text():
    text = "Hello world\nThis is a test"
    task_id = "test_task_txt"
    txt_path = save_text(text, task_id)
    
    assert os.path.exists(txt_path)
    assert txt_path == f"/tmp/{task_id}.txt"
    
    with open(txt_path, "r") as f:
        content = f.read()
        assert content == text
        
    os.remove(txt_path)

def test_format_timestamp():
    assert format_timestamp(0) == "[00:00:00.000]"
    assert format_timestamp(3661.123) == "[01:01:01.123]"
    assert format_timestamp(61.5) == "[00:01:01.500]"

def test_save_timestamped_text():
    segments = [
        {"start": 0.0, "end": 2.5, "text": "Hello world"},
        {"start": 2.5, "end": 5.0, "text": "This is a test"}
    ]
    task_id = "test_task_ts"
    ts_path = save_timestamped_text(segments, task_id)

    assert os.path.exists(ts_path)
    assert ts_path == f"/tmp/{task_id}_timestamps.txt"

    with open(ts_path, "r") as f:
        lines = f.readlines()
        assert len(lines) == 2
        assert "[00:00:00.000] --> [00:00:02.500]  Hello world\n" in lines[0]
        assert "[00:00:02.500] --> [00:00:05.000]  This is a test\n" in lines[1]

    os.remove(ts_path)
