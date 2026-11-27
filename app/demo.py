"""Fictional public fixtures. Never seed an existing personal database."""

import io
import json
import os
from pathlib import Path

from docx import Document
from sqlalchemy import select

from app.cli import initialize
from app.db import transaction
from app.models import Evidence, Job, Profile, Template
from app.schemas import VARIANTS, JobData
from app.services.documents import hyperlink
from app.services.jobs import ingest
from app.services.matching import save_match
from app.services.templates import import_template


def baseline(variant):
    doc = Document()
    doc.add_paragraph("Alex Example")
    contact = doc.add_paragraph()
    hyperlink(contact, "alex@example.invalid | Prague | GitHub", "https://github.com/example")
    doc.add_paragraph("Professional summary")
    doc.add_paragraph(
        {
            "BI Engineering": "Develops Power BI reporting with SQL and DAX.",
            "Data Analytics": "Analyses operational data using SQL and Excel.",
        }.get(variant, "Builds and tests reporting tools in Python and SQL.")
    )
    doc.add_paragraph("Experience")
    doc.add_paragraph("Lantern Transit | Reporting Assistant (part-time) | 2024 – present")
    doc.add_paragraph("• Built SQL views and Power BI reports for service planning.")
    doc.add_paragraph("• Maintained 12 DAX measures in the reporting model.")
    doc.add_paragraph("Fable Studio | Data Intern (part-time) | 2025 – present")
    doc.add_paragraph("• Built a Python validator for incoming timetable records.")
    doc.add_paragraph("Projects")
    hyperlink(
        doc.add_paragraph(), "Timetable Explorer", "https://github.com/example/timetable-explorer"
    )
    doc.add_paragraph("• Published a Python tool for exploring fictional transit schedules.")
    hyperlink(doc.add_paragraph(), "Report Checks", "https://github.com/example/report-checks")
    doc.add_paragraph("• Wrote SQL checks for an example analytics dataset.")
    doc.add_paragraph("Technical skills")
    doc.add_paragraph("Power BI, SQL, DAX, Python, Excel")
    doc.add_paragraph("Education")
    doc.add_paragraph("Example Institute | Applied Computing, studies in progress | 2024 – present")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def demo_jobs():
    path = Path(__file__).resolve().parents[1] / "demo" / "labelled_jobs.json"
    return json.loads(path.read_text())


def seed_session(s, *, evaluation=False):
    candidate = s.get(Profile, 1)
    if (
        any(s.scalar(select(table.id).limit(1)) for table in (Job, Template, Evidence))
        or candidate.name
        or candidate.contact
    ):
        raise ValueError("Fictional seeding requires an empty workspace")
    for variant in VARIANTS:
        if not s.scalar(select(Template.id).where(Template.variant == variant)):
            import_template(s, variant + ".docx", baseline(variant), variant)
    for item in s.scalars(select(Evidence)):
        item.status, item.external = "user_confirmed", True
    s.flush()
    for record in demo_jobs()[: None if evaluation else 4]:
        job = ingest(s, JobData.model_validate(record["job"]))
        save_match(s, job)


def seed():

    base = Path("private/demo-workspace").resolve()
    base.mkdir(mode=0o700, exist_ok=True)
    os.environ["CAREERPILOT_PRIVATE"] = str(base)
    os.environ["DATABASE_URL"] = f"sqlite:///{base}/demo.sqlite3"
    marker = base / ".fictional"
    if (base / "demo.sqlite3").exists() and not marker.exists():
        raise SystemExit("Choose an empty demo directory")
    marker.touch(mode=0o600)
    initialize()
    with transaction() as s:
        if not s.scalar(select(Template.id).limit(1)):
            seed_session(s)
            from app.integrations.mail import ingest_message

            ingest_message(
                s, (Path(__file__).resolve().parents[1] / "demo" / "mail-alert.txt").read_bytes()
            )
    print("Fictional workspace ready. Launch with scripts/start.sh demo.")
