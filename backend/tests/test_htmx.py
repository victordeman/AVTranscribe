import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.src.main import app, get_db
from backend.src.models import Base, Transcription
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

def test_status_polling_queued(client, db_session):
    task_id = "test-queued"
    trans = Transcription(id=task_id, status="queued", progress=0)
    db_session.add(trans)
    db_session.commit()

    response = client.get(f"/status/{task_id}")
    assert response.status_code == 200
    assert 'hx-get="/status/test-queued"' in response.text
    assert 'hx-trigger="every 5s"' in response.text
    assert "bg-yellow-100" in response.text
    assert "In Queue" in response.text

def test_status_polling_processing(client, db_session):
    task_id = "test-processing"
    trans = Transcription(id=task_id, status="processing", progress=3)
    db_session.add(trans)
    db_session.commit()

    response = client.get(f"/status/{task_id}")
    assert response.status_code == 200
    assert 'hx-get="/status/test-processing"' in response.text
    assert 'hx-trigger="every 5s"' in response.text
    assert "bg-blue-100" in response.text
    assert "Transcribing Media" in response.text
    assert "3 segments processed so far" in response.text

def test_status_no_polling_done(client, db_session):
    task_id = "test-done"
    trans = Transcription(id=task_id, status="done", progress=10)
    db_session.add(trans)
    db_session.commit()

    response = client.get(f"/status/{task_id}")
    assert response.status_code == 200
    assert 'hx-get' not in response.text
    assert "bg-green-100" in response.text
    assert "Transcription complete!" in response.text
    assert "Total segments: 10" in response.text

def test_status_no_polling_failed(client, db_session):
    task_id = "test-failed"
    error_msg = "Something went wrong"
    trans = Transcription(id=task_id, status="failed", error_message=error_msg)
    db_session.add(trans)
    db_session.commit()

    response = client.get(f"/status/{task_id}")
    assert response.status_code == 200
    assert 'hx-get' not in response.text
    assert "bg-red-100" in response.text
    assert "Error occurred" in response.text
    assert error_msg in response.text

def test_status_polling_retrying(client, db_session):
    task_id = "test-retrying"
    trans = Transcription(id=task_id, status="retrying (1/3)", progress=0)
    db_session.add(trans)
    db_session.commit()

    response = client.get(f"/status/{task_id}")
    assert response.status_code == 200
    assert 'hx-get="/status/test-retrying"' in response.text
    assert 'hx-trigger="every 5s"' in response.text
    assert "bg-yellow-100" in response.text
    assert "Retrying Task" in response.text
