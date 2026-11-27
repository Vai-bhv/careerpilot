import io

from docx import Document
from sqlalchemy import select

from app.models import Evidence
from app.schemas import JobData
from app.services.jobs import canonical, ingest
from app.services.matching import match
from app.services.templates import import_template


def test_import_is_private_and_idempotent(db):
    word = Document()
    for p in [
        "Alex Example",
        "Experience",
        "Fictional Works | Data Intern (part-time) | 2024 – present",
        "• Built SQL reports.",
        "Projects",
        "Atlas",
        "• Created a Python dashboard.",
    ]:
        word.add_paragraph(p)
    out = io.BytesIO()
    word.save(out)
    a = import_template(db, "source.docx", out.getvalue(), "Data Analytics")
    b = import_template(db, "source.docx", out.getvalue(), "Data Analytics")
    assert a.id == b.id
    rows = list(db.scalars(select(Evidence)))
    assert all(not e.external and e.status == "unverified" for e in rows)
    assert [(e.owner, e.claim) for e in rows if e.kind == "achievement"] == [
        ("Fictional Works", "Built SQL reports.")
    ]


def test_job_provenance_and_unknowns(db):
    from app.models import SourceRecord

    data = JobData(
        title="BI Developer",
        company="Fictional Works",
        description="Požadujeme: Power BI a SQL. Výhodou: Python.",
        url="https://Example.org/job/1/?utm_source=x&id=2",
    )
    job = ingest(db, data)
    assert canonical(data.url) == "https://example.org/job/1?id=2"
    assert job.fields["required"] == ["Power BI", "SQL"] and job.fields["preferred"] == ["Python"]
    assert job.fields["salary_min"] is None
    assert ingest(db, data.model_copy(update={"source": "alert"})).id == job.id
    assert len(list(db.scalars(select(SourceRecord)))) == 2
    result = match(db, job)
    assert result["eligibility"] == "review" and result["technical_score"] == 0


def test_salary_and_distinct_requisitions(db):
    a = JobData(
        title="Analyst",
        company="Fiction",
        source="board",
        external_id="a",
        description="Požadujeme SQL. Plat: 60 000 – 80 000 Kč / měsíc.",
    )
    job = ingest(db, a)
    assert (
        job.fields["salary_min"],
        job.fields["salary_max"],
        job.fields["currency"],
        job.fields["period"],
    ) == (60000, 80000, "CZK", "month")
    second = ingest(db, a.model_copy(update={"external_id": "b"}))
    assert second.id != job.id and second.fields["possible_duplicates"] == [job.id]


def test_question_style_job_sections():
    from app.services.jobs import structured

    job = JobData(
        title="Data Engineer",
        company="Example",
        description="What will you do?\nBuild reporting pipelines.\nWhat are we looking for?\nSQL and Python\nFluent English\nWhat additional skills will help you stand out?\nAirflow\nWork mode\nHybrid",
    )
    fields = structured(job)
    assert fields["required"] == ["SQL", "Python"] and fields["preferred"] == ["Airflow"]
    assert fields["languages"] == ["English"] and fields["arrangement"] == "hybrid"
