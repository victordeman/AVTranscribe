import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.main import app, get_db
from src.models import Base, Transcription
from unittest.mock import patch, MagicMock

# Test Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    app.state.limiter.enabled = False
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Upload Media" in response.text

@patch("src.main.transcribe_task.delay")
@patch("src.main.open", create=True)
def test_transcribe_success(mock_open, mock_delay, client, db_session):
    mock_file = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_file
    
    file_content = b"fake audio content"
    files = {"file": ("test.mp3", file_content, "audio/mpeg")}
    
    response = client.post("/transcribe", files=files, data={"language": "en", "format": "text"})
    
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "queued"
    
    task = db_session.query(Transcription).filter(Transcription.id == data["task_id"]).first()
    assert task is not None
    assert task.status == "queued"
    assert task.filename == "test.mp3"
    assert task.language == "en"
    
    mock_delay.assert_called_once()
    # Check if we wrote to the file
    mock_file.write.assert_called_once_with(file_content)

def test_transcribe_invalid_file(client):
    files = {"file": ("test.txt", b"invalid content", "text/plain")}
    response = client.post("/transcribe", files=files)
    assert response.status_code == 400
    assert "Invalid file" in response.json()["detail"]

def test_get_status_success(client, db_session):
    task_id = "test-task-id"
    trans = Transcription(id=task_id, status="processing")
    db_session.add(trans)
    db_session.commit()
    
    response = client.get(f"/status/{task_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "processing"

def test_get_status_not_found(client):
    response = client.get("/status/non-existent-id")
    assert response.status_code == 404

def test_download_text_success(client, db_session):
    task_id = "done-task-id"
    trans = Transcription(id=task_id, status="done", text="Transcription text")
    db_session.add(trans)
    db_session.commit()
    
    # Ensure the file exists for FileResponse
    file_path = f"/tmp/{task_id}.txt"
    with open(file_path, "w") as f:
        f.write("test content")
    
    try:
        response = client.get(f"/download/{task_id}/text")
        assert response.status_code == 200
        assert response.headers["content-disposition"] == 'attachment; filename="transcription.txt"'
    finally:
        import os
        if os.path.exists(file_path):
            os.remove(file_path)

def test_download_csv_success(client, db_session):
    task_id = "done-task-id-csv"
    csv_path = f"/tmp/{task_id}.csv"
    trans = Transcription(id=task_id, status="done", csv_path=csv_path)
    db_session.add(trans)
    db_session.commit()
    
    # Ensure the file exists for FileResponse
    with open(csv_path, "w") as f:
        f.write("test content")
    
    try:
        response = client.get(f"/download/{task_id}/csv")
        assert response.status_code == 200
        assert response.headers["content-disposition"] == 'attachment; filename="transcription.csv"'
    finally:
        import os
        if os.path.exists(csv_path):
            os.remove(csv_path)

def test_download_not_complete(client, db_session):
    task_id = "pending-task-id"
    trans = Transcription(id=task_id, status="queued")
    db_session.add(trans)
    db_session.commit()
    
    response = client.get(f"/download/{task_id}/text")
    assert response.status_code == 400
    assert "Task not complete" in response.json()["detail"]

def test_download_invalid_format(client, db_session):
    task_id = "done-task-id-fmt"
    trans = Transcription(id=task_id, status="done")
    db_session.add(trans)
    db_session.commit()
    
    response = client.get(f"/download/{task_id}/invalid")
    assert response.status_code == 400
    assert "Invalid format" in response.json()["detail"]
