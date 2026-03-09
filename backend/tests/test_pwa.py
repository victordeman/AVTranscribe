from fastapi.testclient import TestClient
from src.main import app
import os

client = TestClient(app)

def test_pwa_manifest():
    response = client.get("/manifest.json")
    assert response.status_code == 200
    assert response.json()["name"] == "AVTranscribe"
    assert response.json()["short_name"] == "AVTranscribe"

def test_pwa_sw():
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert "application/javascript" in response.headers["content-type"]
    assert "CACHE_NAME" in response.text

def test_pwa_icon():
    response = client.get("/icon.svg")
    assert response.status_code == 200
    assert "image/svg+xml" in response.headers["content-type"]
