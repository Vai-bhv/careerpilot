import io

import pytest
from docx import Document
from sqlalchemy import select

from app.models import Evidence, Profile
from app.repo import Problem, approved
from app.schemas import EvidenceData, JobData
from app.services.jobs import ingest
from app.services.matching import match
from app.services.templates import import_template, review


def source(title, metric):
    d = Document()
    for t in [
        "Alex Example",
        "Experience",
        f"Fable Studio | {title} | 2024 – present",
        f"• Prepared {metric} SQL dashboards each week.",
    ]:
        d.add_paragraph(t)
    out = io.BytesIO()
    d.save(out)
    return out.getvalue()


def test_conflict_resolution(db):
    import_template(db, "old.docx", source("Intern", 12), "Data Analytics")
    import_template(db, "new.docx", source("Analyst", 14), "BI Engineering")
    entries = list(
        db.scalars(select(Evidence).where(Evidence.kind == "employment").order_by(Evidence.id))
    )
    assert all(e.conflict for e in entries)

    def form(row, status):
        return EvidenceData(**{k: getattr(row, k) for k in EvidenceData.model_fields}).model_copy(
            update={"status": status, "external": True}
        )

    with pytest.raises(Problem):
        review(db, entries[1], form(entries[1], "user_confirmed"))
    review(db, entries[0], form(entries[0], "not_approved"))
    review(db, entries[1], form(entries[1], "user_confirmed"))
    assert approved(db) == [entries[1]]


def test_uncertain_duplicate_and_confirmed_eligibility(db):
    a = JobData(
        title="BI Developer",
        company="A",
        location="Prague",
        description="Required: SQL and DAX. Produce regular quarterly revenue reporting for consumers.",
        work_authorisation="authorisation_required",
    )
    first = ingest(db, a)
    second = ingest(db, a.model_copy(update={"description": a.description + " Hybrid."}))
    assert second.id != first.id and second.fields["possible_duplicates"] == [first.id]
    assert match(db, first)["eligibility"] == "review"
    db.get(Profile, 1).preferences = {"work_authorisation": "not_authorised"}
    assert match(db, first)["eligibility"] == "conflict"


def test_demo_cannot_approve_personal_rows(db):
    from app.demo import seed_session

    row = Evidence(
        kind="achievement",
        owner="Private",
        claim="Pending claim",
        source="Local import",
        external=False,
        status="unverified",
    )
    db.add(row)
    with pytest.raises(ValueError, match="empty workspace"):
        seed_session(db)
    assert not row.external and row.status == "unverified"
