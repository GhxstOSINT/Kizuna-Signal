from fastapi.testclient import TestClient

from app.main import app


def test_health():
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_title_validation_rejects_empty_name():
    r = TestClient(app).post("/api/v1/titles", json={"name_en": ""})
    assert r.status_code == 422
