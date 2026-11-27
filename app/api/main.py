import difflib
import json
import logging
import secrets
import time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, File, Form, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import token
from app.db import transaction
from app.integrations.adviser import AISettings, interview, transferable
from app.integrations.boards import Board, state, sync_board
from app.integrations.mail import MAIL_CATEGORIES, SUGGESTED, sync_mail
from app.models import (
    Application,
    Audit,
    Citation,
    Document,
    Evidence,
    Integration,
    Job,
    Mail,
    Match,
    Profile,
    SourceRecord,
    Template,
    Usage,
)
from app.repo import Problem, approved, audit, get, profile, public
from app.scheduler import TASKS, Schedule
from app.schemas import (
    ApplicationView,
    Confirm,
    DocumentView,
    EvidenceApproval,
    EvidenceData,
    EvidenceView,
    Generate,
    JobData,
    MatchView,
    ProfileData,
    Tracking,
    VacancyView,
    Variant,
)
from app.services import documents, jobs, matching, tracking
from app.services.templates import MAX_UPLOAD, import_template, review

app = FastAPI(title="CareerPilot", version="0.1.0")
security = HTTPBearer(auto_error=False)
access = logging.getLogger("uvicorn.error")


@app.middleware("http")
async def request_log(request: Request, call_next):
    started = time.monotonic()
    response = await call_next(request)
    route = request.scope.get("route")
    access.info(
        json.dumps(
            {
                "event": "request",
                "method": request.method,
                "route": getattr(route, "path", "unmatched"),
                "status": response.status_code,
                "elapsed_ms": round(1000 * (time.monotonic() - started)),
            }
        )
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def auth(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)]):
    expected = token()
    if (
        not expected
        or not credentials
        or not secrets.compare_digest(credentials.credentials.encode(), expected.encode())
    ):
        raise Problem("A local workspace bearer token is required", 401)


def session(request: Request):
    with transaction() as s:
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            s.execute(update(Profile).where(Profile.id == 1).values(id=1))
        yield s


DB = Annotated[Session, Depends(session, scope="function")]
router = APIRouter(prefix="/v1", dependencies=[Depends(auth)])
Limit = Annotated[int, Query(ge=1, le=500)]
Offset = Annotated[int, Query(ge=0)]


@app.exception_handler(Problem)
def problem(_, exc):
    return JSONResponse({"detail": str(exc)}, status_code=exc.status)


@app.exception_handler(RequestValidationError)
def invalid(_, exc):
    return JSONResponse(
        {"detail": "Invalid input", "fields": [list(e["loc"]) for e in exc.errors()]},
        status_code=422,
    )


@app.exception_handler(IntegrityError)
def contention(_, exc):
    return JSONResponse(
        {"detail": "A concurrent or duplicate change conflicts with this request"}, status_code=409
    )


@app.get("/health/live")
def live():
    return {"status": "live"}


@app.get("/health/ready")
def ready():
    try:
        with transaction() as s:
            if (
                s.scalar(text("select version_num from alembic_version")) != "b4c11f4b0ae2"
                or s.get(Profile, 1) is None
            ):
                raise Problem("Initialize the workspace first", 503)
    except SQLAlchemyError:
        raise Problem("Database unavailable or migrations pending", 503) from None
    return {"status": "ready"}


@router.get("/profile")
def get_profile(s: DB) -> ProfileData:
    return ProfileData.model_validate(public(profile(s), ("id", "created")))


@router.put("/profile")
def set_profile(data: ProfileData, s: DB) -> ProfileData:
    p = profile(s)
    for k, v in data.model_dump().items():
        setattr(p, k, v)
    matching.refresh_evaluations(s)
    audit(s, "profile.update", p.id)
    return data


@router.get("/evidence", response_model=list[EvidenceView])
def evidence(s: DB, allowed: bool = False, limit: Limit = 200, offset: Offset = 0) -> list[dict]:
    rows = (
        approved(s)[offset : offset + limit]
        if allowed
        else s.scalars(select(Evidence).order_by(Evidence.id).limit(limit).offset(offset))
    )
    return [public(e) for e in rows]


@router.post("/evidence", response_model=EvidenceView)
def add_evidence(data: EvidenceData, s: DB) -> dict:
    row = Evidence(**data.model_dump())
    s.add(row)
    s.flush()
    return public(review(s, row, data))


@router.post("/evidence/approve-selected")
def approve_selected(data: EvidenceApproval, s: DB) -> dict:
    rows = []
    for key, expected in sorted(data.claims.items()):
        row = get(s, Evidence, key, lock=True)
        current = EvidenceData(
            **{field: getattr(row, field) for field in EvidenceData.model_fields}
        )
        if current != expected or row.conflict or row.status in {"confidential", "not_approved"}:
            raise Problem(f"Evidence #{key} changed or requires individual review", 409)
        rows.append((row, current))
    for row, current in rows:
        review(s, row, current.model_copy(update={"status": "user_confirmed", "external": True}))
    return {"approved": len(rows)}


@router.put("/evidence/{key}", response_model=EvidenceView)
def update_evidence(key: int, data: EvidenceData, s: DB) -> dict:
    return public(review(s, get(s, Evidence, key, lock=True), data))


@router.get("/templates")
def templates(s: DB) -> list[dict]:
    return [
        public(t, ("content", "paragraphs"))
        for t in s.scalars(select(Template).order_by(Template.id))
    ]


@router.get("/templates/{key}")
def template_detail(key: int, s: DB) -> dict:
    result = public(get(s, Template, key), ("content",))
    result["citations"] = [
        public(r) for r in s.scalars(select(Citation).where(Citation.template_id == key))
    ]
    return result


@router.post("/templates")
def upload(s: DB, variant: Annotated[Variant, Form()], file: Annotated[UploadFile, File()]) -> dict:
    return public(
        import_template(s, file.filename or "", file.file.read(MAX_UPLOAD + 1), variant),
        ("content", "paragraphs"),
    )


@router.post("/jobs", response_model=VacancyView)
def import_job(data: JobData, s: DB) -> dict:
    return public(jobs.ingest(s, data))


@router.post("/imports")
def bulk(data: list[dict], s: DB) -> list[dict]:
    return jobs.import_rows(s, data)


@router.get("/jobs", response_model=list[VacancyView])
def search(
    s: DB,
    q: str = "",
    company: str = "",
    location: str = "",
    source: str = "",
    status: str = "",
    limit: Limit = 50,
    offset: Offset = 0,
    min_score: Annotated[int, Query(ge=0, le=100)] = 0,
    category: Variant | None = None,
    within_days: Annotated[int | None, Query(ge=1, le=3650)] = None,
) -> list[dict]:
    return jobs.find_jobs(
        s, q, company, location, source, status, limit, offset, min_score, category, within_days
    )


@router.get("/jobs/{key}")
def details(key: int, s: DB) -> dict:
    job = get(s, Job, key)
    return {
        **public(job),
        "sources": [
            public(x) for x in s.scalars(select(SourceRecord).where(SourceRecord.job_id == key))
        ],
    }


@router.get("/jobs/{key}/match", response_model=MatchView)
def explain(key: int, s: DB) -> dict:
    return matching.match(s, get(s, Job, key))


@router.post("/jobs/{key}/match", response_model=MatchView)
def evaluate(key: int, s: DB) -> dict:
    return matching.save_match(s, get(s, Job, key, lock=True))


@router.get("/jobs/{key}/transferable")
def transferable_skills(key: int, s: DB) -> dict:
    return transferable(s, get(s, Job, key))


@router.get("/rankings")
def rankings(s: DB, limit: Limit = 50, offset: Offset = 0) -> list[dict]:
    rows = [{"job_id": r.job_id, **r.result} for r in s.scalars(select(Match))]
    return sorted(rows, key=lambda r: (r["eligibility"] == "conflict", -r["score"], r["job_id"]))[
        offset : offset + limit
    ]


@router.get("/jobs/{key}/interview")
def questions(key: int, s: DB) -> dict:
    return interview(get(s, Job, key))


@router.post("/jobs/{key}/documents", response_model=DocumentView)
def generate_doc(key: int, data: Generate, s: DB) -> dict:
    return public(documents.generate(s, get(s, Job, key, lock=True), data), ("docx", "pdf"))


@router.get("/jobs/{key}/documents", response_model=list[DocumentView])
def versions(key: int, s: DB) -> list[dict]:
    return [
        public(d, ("docx", "pdf"))
        for d in s.scalars(
            select(Document).where(Document.job_id == key).order_by(Document.id.desc())
        )
    ]


@router.get("/documents/{key}/validate")
def validate_doc(key: int, s: DB) -> dict:
    errors = documents.validate(s, get(s, Document, key))
    return {"valid": not errors, "errors": errors}


@router.post("/documents/{key}/approve")
def approve_doc(key: int, s: DB) -> dict:
    doc = documents.approve(s, get(s, Document, key, lock=True))
    job = get(s, Job, doc.job_id)
    if doc.kind == "cv" and job.status in tracking.PRE:
        from app.repo import set_stage

        set_stage(s, job, "ready_to_apply")
    return {"id": doc.id, "approved": doc.approved}


@router.get("/documents/{key}/compare")
def compare(key: int, s: DB, previous: int | None = None) -> dict:
    doc = get(s, Document, key)
    if previous:
        other = get(s, Document, previous)
        if other.job_id != doc.job_id:
            raise Problem("Choose a version of this vacancy")
        before = other.plain
    elif doc.snapshot.get("template_id"):
        before = "\n".join(
            line for line, _ in get(s, Template, doc.snapshot["template_id"]).paragraphs
        )
    else:
        before = ""
    return {
        "original": before,
        "tailored": doc.plain,
        "diff": list(
            difflib.unified_diff(before.splitlines(), doc.plain.splitlines(), lineterm="")
        ),
    }


@router.get("/documents/{key}/download/{fmt}")
def download(key: int, fmt: Literal["txt", "json", "docx", "pdf"], s: DB):
    doc = get(s, Document, key)
    if documents.validate(s, doc):
        raise Problem("Revalidate and regenerate this document before export", 409)
    data = {
        "txt": lambda: doc.plain,
        "json": lambda: json.dumps(doc.snapshot, ensure_ascii=False),
        "pdf": lambda: doc.pdf,
        "docx": lambda: doc.docx,
    }[fmt]()
    if data is None:
        raise Problem("Format unavailable for this document", 404)
    return Response(
        data,
        media_type={
            "txt": "text/plain",
            "json": "application/json",
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }[fmt],
        headers={
            "Content-Disposition": f'attachment; filename="careerpilot-{key}.{fmt}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/jobs/{key}/prepare")
def prepare(key: int, s: DB) -> dict:
    job = get(s, Job, key)
    docs = [
        d
        for d in versions(key, s)
        if d["approved"] and not documents.validate(s, get(s, Document, d["id"]))
    ]
    return {
        "job_id": key,
        "application_url": job.apply_url,
        "documents": docs,
        "ready": any(d["kind"] == "cv" for d in docs) and job.status in tracking.PRE,
    }


@router.put("/jobs/{key}/tracking", response_model=ApplicationView)
def change_status(key: int, data: Tracking, s: DB) -> dict:
    return public(tracking.track(s, get(s, Job, key, lock=True), data))


@router.post("/jobs/{key}/confirm", response_model=ApplicationView)
def confirm_submission(key: int, data: Confirm, s: DB) -> dict:
    return public(tracking.confirm(s, get(s, Job, key, lock=True), data))


@router.get("/jobs/{key}/timeline")
def timeline(key: int, s: DB) -> list[dict]:
    return tracking.timeline(s, get(s, Job, key))


@router.get("/applications")
def applications(s: DB, status: str = "", limit: Limit = 50, offset: Offset = 0) -> list[dict]:
    stmt = select(Application, Job).join(Job)
    if status:
        stmt = stmt.where(Application.status == status)
    return [
        {**public(a), "title": j.title, "company": j.company}
        for a, j in s.execute(stmt.order_by(Application.id.desc()).limit(limit).offset(offset))
    ]


@router.get("/statistics")
def stats(s: DB) -> dict:
    return tracking.statistics(s)


@router.get("/skills")
def skills_report(s: DB, shortlisted: bool = False, role: str = "") -> dict:
    return matching.gaps(s, shortlisted, role)


@router.get("/integrations")
def integrations(s: DB) -> list[dict]:
    return [public(r) for r in s.scalars(select(Integration))]


@router.put("/integrations/board")
def configure_board(data: Board, enabled: bool, s: DB) -> dict:
    row = state(s, f"{data.platform}/{data.slug}")
    row.state = {**row.state, "board": data.model_dump(), "enabled": enabled}
    return row.state


@router.post("/integrations/board")
def read_board(data: Board, s: DB) -> dict:
    return sync_board(s, data)


@router.post("/integrations/yahoo")
def read_mail(s: DB) -> dict:
    return sync_mail(s)


@router.get("/communications")
def communications(s: DB, limit: Limit = 100, offset: Offset = 0) -> list[dict]:
    return [
        {**public(m), "suggested_status": SUGGESTED.get(m.category)}
        for m in s.scalars(select(Mail).order_by(Mail.id.desc()).limit(limit).offset(offset))
    ]


@router.put("/communications/{key}/classification")
def classify_communication(key: int, category: str, s: DB) -> dict:
    if category not in MAIL_CATEGORIES:
        raise Problem("Unknown recruitment classification")
    item = get(s, Mail, key, lock=True)
    previous = item.category
    item.category = category
    item.confidence = 1.0
    audit(s, "mail.classification_corrected", item.id, previous=previous, category=category)
    return {"category": category}


@router.put("/communications/{key}/job/{job_id}")
def associate(key: int, job_id: int, s: DB) -> dict:
    m = get(s, Mail, key)
    job = get(s, Job, job_id)
    m.job_id = job.id
    audit(s, "mail.link", f"job/{job.id}", communication=m.id, category=m.category)
    return public(m)


@router.put("/schedules/{task}")
def schedule(task: str, data: Schedule, s: DB) -> dict:
    if task not in TASKS:
        raise Problem("Unknown schedule")
    item = state(s, "schedule/" + task)
    item.state = data.model_dump()
    return item.state


@router.get("/history")
def history(s: DB, limit: Limit = 50) -> list[dict]:
    return [
        public(a)
        for a in s.scalars(
            select(Audit)
            .where(
                Audit.action.in_(
                    [
                        "source.sync",
                        "mail.sync_error",
                        "mail.sync",
                        "schedule.error",
                        "schedule.run",
                        "ingest.invalid",
                    ]
                )
            )
            .order_by(Audit.id.desc())
            .limit(limit)
        )
    ]


@router.get("/usage")
def usage(s: DB, limit: Limit = 50) -> list[dict]:
    return [public(u) for u in s.scalars(select(Usage).order_by(Usage.id.desc()).limit(limit))]


@router.get("/profile/history")
def professional_history(s: DB) -> dict:
    from app.services.profile import structured_profile

    return structured_profile(s)


@router.post("/communications/{key}/vacancies")
def import_alert(key: int, data: JobData, s: DB) -> dict:
    message = get(s, Mail, key)
    if data.url not in message.links:
        raise Problem("Select a link from this alert")
    job = jobs.ingest(s, data.model_copy(update={"source": "mail_alert", "external_id": None}))
    audit(s, "mail.vacancy", f"job/{job.id}", communication=message.id)
    return public(job)


@router.get("/ai-settings")
def ai_settings(s: DB) -> dict:
    from app.integrations.adviser import settings

    return settings(s).model_dump()


@router.put("/ai-settings")
def save_ai_settings(data: AISettings, s: DB) -> dict:
    row = state(s, "ai-settings")
    row.state = data.model_dump()
    return row.state


app.include_router(router)


@app.get("/thunderbird/status")
def thunderbird_status(request: Request):
    from app.integrations.thunderbird import authorize

    authorize(request.headers.get("authorization", ""), request.headers.get("origin"))
    return {"status": "paired"}


@app.post("/thunderbird/messages")
async def thunderbird_message(request: Request):
    from starlette.concurrency import run_in_threadpool

    from app.integrations.thunderbird import MAX_REQUEST, authorize, import_payload

    authorize(request.headers.get("authorization", ""), request.headers.get("origin"))
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_REQUEST:
            raise Problem("Message exceeds the import limit", 413)
        data.extend(chunk)

    def store():
        with transaction() as s:
            s.execute(update(Profile).where(Profile.id == 1).values(id=1))
            return import_payload(s, data)

    return await run_in_threadpool(store)
