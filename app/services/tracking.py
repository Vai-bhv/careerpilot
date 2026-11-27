from collections import Counter
from datetime import date

from sqlalchemy import select

from app.db import now
from app.models import Application, Audit, Document, Job, Match
from app.repo import Problem, audit, get, public
from app.services.documents import validate

PRE = {
    "discovered",
    "evaluated",
    "shortlisted",
    "cv_generated",
    "awaiting_approval",
    "ready_to_apply",
}
POST = {
    "recruiter_responded",
    "screening",
    "technical_interview",
    "final_interview",
    "offer_received",
    "rejected",
}
TERMINAL = {"rejected", "withdrawn", "expired"}


def application(s, job):
    return s.scalar(select(Application).where(Application.job_id == job.id))


def track(s, job, data):
    app = application(s, job)
    old = app.status if app else job.status
    if data.status == "applied" or (data.status in POST and not (app and app.submitted)):
        raise Problem("Confirm an actual submission with approved document versions first", 409)
    if old in TERMINAL and data.status != old or (app and app.submitted and data.status in PRE):
        raise Problem("This transition would invalidate application history", 409)
    if data.status == "ready_to_apply" and not any(
        not validate(s, d)
        for d in s.scalars(
            select(Document).where(
                Document.job_id == job.id, Document.approved.is_(True), Document.kind == "cv"
            )
        )
    ):
        raise Problem("Approve a current CV for this vacancy first", 409)
    if not app:
        app = Application(job_id=job.id, status=data.status)
        s.add(app)
    app.status = job.status = data.status
    app.details = {
        **(app.details or {}),
        **data.model_dump(mode="json", exclude={"status"}, exclude_unset=True),
    }
    audit(
        s,
        "application.update",
        f"job/{job.id}",
        previous=old,
        status=data.status,
        details=app.details,
    )
    s.flush()
    return app


def check_doc(s, key, job, kind):
    doc = get(s, Document, key, lock=True)
    if doc.job_id != job.id or doc.kind != kind or not doc.approved or validate(s, doc):
        raise Problem("Choose an approved, currently valid document for this vacancy", 409)
    return doc


def confirm(s, job, data):
    if job.status in TERMINAL:
        raise Problem("Vacancy is closed", 409)
    app = application(s, job)
    if app and app.submitted:
        raise Problem("Submission already recorded", 409)
    check_doc(s, data.cv_id, job, "cv")
    if data.letter_id:
        check_doc(s, data.letter_id, job, "cover_letter")
    if not app:
        app = Application(job_id=job.id, status="applied")
        s.add(app)
    app.cv_id, app.letter_id = data.cv_id, data.letter_id
    app.submitted = now()
    app.status = job.status = "applied"
    app.details = {
        **(app.details or {}),
        "method": data.method,
        "company_at_submission": job.company,
        "title_at_submission": job.title,
    }
    audit(
        s,
        "application.confirm",
        f"job/{job.id}",
        cv=data.cv_id,
        letter=data.letter_id,
        method=data.method,
    )
    s.flush()
    return app


def timeline(s, job):
    return [
        public(a)
        for a in s.scalars(select(Audit).where(Audit.entity == f"job/{job.id}").order_by(Audit.id))
    ]


def statistics(s):
    jobs = list(s.scalars(select(Job)))
    apps = list(s.scalars(select(Application)))
    stages = Counter(j.status for j in jobs)
    return {
        "vacancies": len(jobs),
        "new": stages["discovered"],
        "strong_matches": sum(r.result["fit"] == "strong" for r in s.scalars(select(Match))),
        "submitted": sum(a.submitted is not None for a in apps),
        "interviews": sum(
            a.status in {"screening", "technical_interview", "final_interview"} for a in apps
        ),
        "follow_ups": sum(
            bool(a.details.get("follow_up"))
            and a.details["follow_up"] <= date.today().isoformat()
            and a.status not in TERMINAL
            for a in apps
        ),
        "funnel": dict(stages),
    }
