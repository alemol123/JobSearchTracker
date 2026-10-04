import pytest

from db import connect, db_path, init_db


@pytest.fixture
def conn(tmp_path):
    """A real SQLite database in a temporary folder, fresh for every test."""
    path = db_path(tmp_path)
    init_db(path)
    connection = connect(path)
    yield connection
    connection.close()
