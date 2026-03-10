import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.src.main import app, get_db
from backend.src.models import Base, Transcription, User
from backend.src.auth import get_current_user
from unittest.mock import patch, MagicMock
import os

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

@pytest.fixture(scope="function")
def authenticated_client(client, db_session):
    user = User(username="testuser", hashed_password="fakehashedpassword")
    db_session.add(user)
    db_session.commit()

    from backend.src.main import get_current_user as gcu

    def override_get_current_user():
        return user

    app.dependency_overrides[gcu] = override_get_current_user
    yield client
    del app.dependency_overrides[gcu]

def test_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Upload Media" in response.text or 'id="root"' in response.text

def test_signup(client, db_session):
    response = client.post("/signup", data={"username": "newuser", "password": "newpassword"})
    assert response.status_code == 200
    assert response.json()["message"] == "User created successfully"
    user = db_session.query(User).filter(User.username == "newuser").first()
    assert user is not None

def test_login(client, db_session):
    from backend.src.auth import get_password_hash
    user = User(username="loginuser", hashed_password=get_password_hash("loginpassword"))
    db_session.add(user)
    db_session.commit()

    response = client.post("/login", data={"username": "loginuser", "password": "loginpassword"})
    assert response.status_code == 200
    assert "access_token" in response.json()

@patch("backend.src.main.transcribe_with_whisper")
@patch("backend.src.main.open", create=True)
def test_transcribe_success(mock_open, mock_transcribe, authenticated_client, db_session):
    mock_file = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_file
    
    mock_transcribe.return_value = {"text": "Hello world", "segments": []}

    file_content = b"fake audio content"
    files = {"file": ("test.mp3", file_content, "audio/mpeg")}
    
    response = authenticated_client.post("/transcribe", files=files, data={"language": "en", "format": "text"})
    
    assert response.status_code == 200
    assert "Transcription Status" in response.text
    assert "queued" in response.text
    
    task = db_session.query(Transcription).first()
    assert task is not None
    assert task.status == "queued"
    mock_file.write.assert_called_once_with(file_content)

def test_transcribe_unauthenticated(client):
    files = {"file": ("test.mp3", b"fake audio", "audio/mpeg")}
    response = client.post("/transcribe", files=files)
    assert response.status_code == 401

def test_transcribe_invalid_file(authenticated_client):
    files = {"file": ("test.txt", b"invalid content", "text/plain")}
    response = authenticated_client.post("/transcribe", files=files)
    assert response.status_code == 400
    assert "Invalid file" in response.json()["detail"]

def test_get_status_success(client, db_session):
    task_id = "test-task-id"
    trans = Transcription(id=task_id, status="processing", progress=5)
    db_session.add(trans)
    db_session.commit()
    
    response = client.get(f"/status/{task_id}")
    assert response.status_code == 200
    assert "processing" in response.text
    assert "5 segments" in response.text

def test_get_status_not_found(client):
    response = client.get("/status/non-existent-id")
    assert response.status_code == 404

def test_download_text_success(client, db_session):
    task_id = "done-task-id"
    trans = Transcription(id=task_id, status="done", text="Transcription text")
    db_session.add(trans)
    db_session.commit()
    
    file_path = f"/tmp/{task_id}.txt"
    with open(file_path, "w") as f:
        f.write("test content")
    
    try:
        response = client.get(f"/download/{task_id}/text")
        assert response.status_code == 200
        assert response.headers["content-disposition"] == 'attachment; filename="transcription.txt"'
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

def test_download_csv_success(client, db_session):
    task_id = "done-task-id-csv"
    csv_path = f"/tmp/{task_id}.csv"
    trans = Transcription(id=task_id, status="done", csv_path=csv_path)
    db_session.add(trans)
    db_session.commit()
    
    with open(csv_path, "w") as f:
        f.write("test content")
    
    try:
        response = client.get(f"/download/{task_id}/csv")
        assert response.status_code == 200
        assert response.headers["content-disposition"] == 'attachment; filename="transcription.csv"'
    finally:
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
