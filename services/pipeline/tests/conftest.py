import pytest

from app import create_app
from db import connect, db_path, init_db


@pytest.fixture
def conn(tmp_path):
    """A real SQLite database in a temporary folder, fresh for every test."""
    path = db_path(tmp_path)
    init_db(path)
    connection = connect(path)
    yield connection
    connection.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A Flask test client for an app whose database lives in a temporary folder."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()
