from fastapi.testclient import TestClient

from app.api.main import app
from app.db import transaction
from app.demo import seed_session


def test_human_workflow(workspace):
    c = TestClient(app)
    assert c.get("/health/ready").status_code == 200
    assert c.get("/v1/jobs").status_code == 401
    c.headers["Authorization"] = "Bearer synthetic-local-test-token"
    with transaction() as s:
        seed_session(s)
    j = c.get("/v1/jobs", params={"q": "Power BI Developer", "limit": 1}).json()[0]
    root = f"/v1/jobs/{j['id']}"
    assert c.post(root + "/match").json()["variant"] == "BI Engineering"
    assert c.put(root + "/tracking", json={"status": "shortlisted"}).status_code == 200
    d = c.post(root + "/documents", json={}).json()
    assert c.get(f"/v1/documents/{d['id']}/download/pdf").content.startswith(b"%PDF")
    assert not c.get(root + "/prepare").json()["ready"]
    assert c.post(f"/v1/documents/{d['id']}/approve").status_code == 200
    assert c.get(root + "/prepare").json()["ready"]
    assert c.post(root + "/confirm", json={"cv_id": d["id"], "confirmed": False}).status_code == 422
    assert c.post(root + "/confirm", json={"cv_id": d["id"], "confirmed": True}).status_code == 200
    assert c.post(root + "/confirm", json={"cv_id": d["id"], "confirmed": True}).status_code == 409
    assert c.get("/v1/applications").json()[0]["cv_id"] == d["id"]
    assert c.put(root + "/tracking", json={"status": "technical_interview"}).status_code == 200
    assert (
        sum(a["action"].startswith("application.") for a in c.get(root + "/timeline").json()) == 3
    )
    assert c.get("/v1/statistics").json()["interviews"] == 1
    assert c.get("/v1/jobs", params={"limit": -1}).status_code == 422


def test_import_rejects_invalid_records(workspace):
    c = TestClient(app, headers={"Authorization": "Bearer synthetic-local-test-token"})
    data = {
        "title": "Data Analyst",
        "company": "Fiction Co",
        "description": "Required: Excel, SQL.",
    }
    rows = c.post("/v1/imports", json=[data, {**data, "apply_url": "javascript:alert(1)"}]).json()
    assert rows[0]["id"] and "error" in rows[1]
    assert len(c.get("/v1/jobs").json()) == 1
    response = c.post(
        "/v1/jobs", json={**data, "url": "https://user:private-value@example.invalid/"}
    )
    assert response.status_code == 422 and "private-value" not in response.text


def test_batch_approval_and_existing_cv(workspace):
    from app.schemas import EvidenceData

    c = TestClient(app, headers={"Authorization": "Bearer synthetic-local-test-token"})
    claim = EvidenceData(
        kind="identity", owner="Candidate", claim="Synthetic Name", source="Fixture"
    )
    created = c.post("/v1/evidence", json=claim.model_dump()).json()
    key = str(created["id"])
    url = "/v1/evidence/approve-selected"
    assert (
        c.post(
            url, json={"confirmed": True, "claims": {key: {**claim.model_dump(), "claim": "Stale"}}}
        ).status_code
        == 409
    )
    assert c.post(url, json={"confirmed": True, "claims": {key: claim.model_dump()}}).json() == {
        "approved": 1
    }
    job = c.post(
        "/v1/jobs",
        json={"title": "Analyst", "company": "Example", "description": "Required: SQL and Excel."},
    ).json()
    endpoint = f"/v1/jobs/{job['id']}/confirm"
    payload = {"confirmed": True, "existing_cv": "Analytics rev 2.pdf"}
    record = c.post(endpoint, json=payload)
    assert record.status_code == 200
    assert record.json()["details"]["existing_cv"] == payload["existing_cv"]
    assert c.post(endpoint, json=payload).status_code == 409
