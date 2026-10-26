"""Point the app at a throw-away copy of the SQLite DB and model dir *before* it is imported."""

import os
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("apitest")
    shutil.copy(REPO_ROOT / "retail_sales.db", tmp / "retail_sales.db")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp / 'retail_sales.db'}"
    os.environ["MODEL_DIR"] = str(tmp / "models")

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:  # runs lifespan: creates tables, trains models
        yield c
