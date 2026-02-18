import sys
from unittest.mock import MagicMock

# Mock modules that are hard to install
sys.modules["whisper"] = MagicMock()
sys.modules["torch"] = MagicMock()
sys.modules["moviepy"] = MagicMock()
sys.modules["moviepy.editor"] = MagicMock()
sys.modules["pydub"] = MagicMock()

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from src.main import app, get_db
from src.models import Base, engine, SessionLocal
import os

# Setup test database
Base.metadata.create_all(bind=engine)

client = TestClient(app)

def test_home():
    response = client.get("/")
    assert response.status_code == 200
    assert "Upload Media" in response.text

@patch("src.main.transcribe_task.delay")
def test_transcribe(mock_task):
    mock_task.return_value = MagicMock(id="test-task-id")

    # Create a dummy file
    test_file_path = "test_audio.mp3"
    with open(test_file_path, "wb") as f:
        f.write(b"dummy audio content")

    try:
        with open(test_file_path, "rb") as f:
            response = client.post(
                "/transcribe",
                files={"file": ("test_audio.mp3", f, "audio/mpeg")},
                data={"language": "en", "format": "audio"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "queued"
        mock_task.assert_called_once()
    finally:
        if os.path.exists(test_file_path):
            os.remove(test_file_path)

def test_status_not_found():
    response = client.get("/status/non-existent-id")
    assert response.status_code == 404

def test_download_not_found():
    response = client.get("/download/non-existent-id/text")
    assert response.status_code == 404
