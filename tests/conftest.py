from __future__ import annotations

import os
from pathlib import Path

import pytest

TEST_DB = Path(__file__).resolve().parent / "test_kizuna.db"
os.environ["KIZUNA_DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["KIZUNA_DEMO_MODE"] = "true"
os.environ["KIZUNA_FRONTEND_MODE"] = "mock"  # legacy Streamlit tests must not pick up a locally running API
os.environ["KIZUNA_SOURCE_CACHE_DIR"] = ""
os.environ["KIZUNA_LIVE_SOURCES"] = "false"  # tests never touch the network

from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def title_payload():
    return {
        "name": "Shadow Bloom",
        "english_title": "Shadow Bloom",
        "synopsis": (
            "A teenage spirit guardian must protect her city while learning to trust a group "
            "of unlikely friends caught between the human world and an ancient supernatural war."
        ),
        "content_format": "anime_series",
        "primary_genre": "fantasy",
        "genres": ["fantasy", "action", "drama"],
        "themes": ["friendship", "spirits", "coming of age"],
        "source_material": "original",
        "expected_release_period": "March 2027",
        "target_platform": "OTT",
        "target_languages": ["Hindi", "Tamil", "Telugu"],
        "target_states": ["Maharashtra", "Karnataka", "Tamil Nadu"],
        "marketing_budget": "medium",
        "studio": "Hikari Studio",
        "franchise_status": "standalone",
    }


@pytest.fixture
def created_title(client, title_payload):
    project = client.post("/api/v1/projects", json={"name": "India Launch Slate"})
    assert project.status_code == 201
    title = client.post(
        f"/api/v1/projects/{project.json()['id']}/titles",
        json=title_payload,
    )
    assert title.status_code == 201
    return title.json()
