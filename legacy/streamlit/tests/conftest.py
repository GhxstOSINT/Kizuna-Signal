"""Test setup: pins the mock client and provides a TestClient for the one test that drives the backend."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

TEST_DB = Path(__file__).resolve().parent / "test_kizuna.db"
os.environ["KIZUNA_DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["KIZUNA_DEMO_MODE"] = "true"
# "auto" would pick up any API already listening on localhost:8000 and change the page-render results.
os.environ.setdefault("KIZUNA_FRONTEND_MODE", "mock")

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
