import os

import pytest
from sqlalchemy import inspect

from app.cli import initialize
from app.db import engine_for, transaction
from app.demo import seed_session
from app.services.jobs import find_jobs


@pytest.mark.skipif(
    not os.getenv("CAREERPILOT_TEST_POSTGRES"),
    reason="Requires a dedicated empty PostgreSQL database",
)
def test_postgres_migration_and_search(tmp_path, monkeypatch):
    url = os.environ["CAREERPILOT_TEST_POSTGRES"]
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("CAREERPILOT_PRIVATE", str(tmp_path))
    engine = engine_for(url)
    assert not inspect(engine).get_table_names(), "Use a fresh disposable database"
    initialize()
    initialize()
    with transaction() as s:
        seed_session(s)
        assert find_jobs(s, q="DAX")[0]["title"] == "Power BI Developer"
    assert "alembic_version" in inspect(engine).get_table_names()
