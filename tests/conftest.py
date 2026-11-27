import pytest

from app.cli import initialize
from app.db import transaction


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("CAREERPILOT_PRIVATE", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/workspace.db")
    monkeypatch.setenv("CAREERPILOT_TOKEN", "synthetic-local-test-token")
    initialize()
    yield tmp_path


@pytest.fixture
def db(workspace):
    with transaction() as session:
        yield session
