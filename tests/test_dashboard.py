from pathlib import Path

from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from app.api.main import app
from app.client import WorkspaceAPI
from app.db import transaction
from app.demo import seed_session
from app.integrations.mail import ingest_message


def test_all_views_with_fictional_data(workspace, monkeypatch):
    with transaction() as s:
        seed_session(s)
        ingest_message(s, Path("tests/fixtures/recruitment.eml").read_bytes())
    client = TestClient(app, headers={"Authorization": "Bearer synthetic-local-test-token"})

    def local_request(self, method, path, **kwargs):
        response = client.request(method, "/v1" + path, **kwargs)
        return response.raise_for_status()

    monkeypatch.setattr(WorkspaceAPI, "request", local_request)
    dashboard = AppTest.from_file(Path("frontend/dashboard.py").resolve(), default_timeout=10).run()
    assert not dashboard.exception and not dashboard.error
    for page in dashboard.radio(key="nav").options:
        dashboard.radio(key="nav").set_value(page).run()
        assert not dashboard.exception and not dashboard.error, page
