from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, now


class Row(Base):
    __abstract__ = True
    id: Mapped[int] = mapped_column(primary_key=True)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Profile(Row):
    __tablename__ = "profiles"
    name: Mapped[str] = mapped_column(default="")
    contact: Mapped[str] = mapped_column(default="")
    github: Mapped[str] = mapped_column(default="")
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)


class Template(Row):
    __tablename__ = "cv_templates"
    variant: Mapped[str]
    digest: Mapped[str] = mapped_column(String(64), index=True)
    __table_args__ = (UniqueConstraint("variant", "digest"),)
    filename: Mapped[str]
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    paragraphs: Mapped[list] = mapped_column(JSON)


class Evidence(Row):
    __tablename__ = "evidence"
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), default=1)
    kind: Mapped[str] = mapped_column(index=True)
    owner: Mapped[str]
    claim: Mapped[str] = mapped_column(Text)
    source: Mapped[str]
    status: Mapped[str] = mapped_column(default="unverified")
    external: Mapped[bool] = mapped_column(default=False)
    technologies: Mapped[list] = mapped_column(JSON, default=list)
    roles: Mapped[list] = mapped_column(JSON, default=list)
    link: Mapped[str] = mapped_column(default="")
    metric: Mapped[str] = mapped_column(default="")
    notes: Mapped[str] = mapped_column(default="")
    conflict: Mapped[bool] = mapped_column(default=False)


class Citation(Row):
    __tablename__ = "template_citations"
    template_id: Mapped[int] = mapped_column(ForeignKey("cv_templates.id"))
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id"), index=True)
    paragraph: Mapped[int]
    __table_args__ = (UniqueConstraint("template_id", "paragraph"),)


class Job(Row):
    __tablename__ = "vacancies"
    title: Mapped[str] = mapped_column(index=True)
    company: Mapped[str] = mapped_column(index=True)
    location: Mapped[str | None] = mapped_column(index=True)
    url: Mapped[str | None] = mapped_column(index=True)
    apply_url: Mapped[str | None]
    description: Mapped[str] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    fields: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(default="discovered")
    checked: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SourceRecord(Row):
    __tablename__ = "source_records"
    source: Mapped[str]
    identity: Mapped[str]
    job_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("source", "identity"),)


class Match(Row):
    __tablename__ = "matches"
    job_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), unique=True)
    result: Mapped[dict] = mapped_column(JSON)


class Document(Row):
    __tablename__ = "documents"
    job_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), index=True)
    kind: Mapped[str]
    snapshot: Mapped[dict] = mapped_column(JSON)
    plain: Mapped[str] = mapped_column(Text)
    docx: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    pdf: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    approved: Mapped[bool] = mapped_column(default=False)


class Application(Row):
    __tablename__ = "applications"
    job_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), unique=True)
    status: Mapped[str]
    cv_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    letter_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    submitted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class Mail(Row):
    __tablename__ = "communications"
    message_key: Mapped[str] = mapped_column(String(64), unique=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("vacancies.id"))
    subject: Mapped[str]
    category: Mapped[str]
    confidence: Mapped[float]
    links: Mapped[list] = mapped_column(JSON)
    summary: Mapped[str] = mapped_column(Text)


class Integration(Row):
    __tablename__ = "integrations"
    name: Mapped[str] = mapped_column(unique=True)
    state: Mapped[dict] = mapped_column(JSON, default=dict)


class Audit(Row):
    __tablename__ = "audit"
    action: Mapped[str] = mapped_column(index=True)
    entity: Mapped[str] = mapped_column(index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class Usage(Row):
    __tablename__ = "llm_usage"
    cache_key: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str]
    tokens: Mapped[int]
    cost: Mapped[float]
    result: Mapped[dict] = mapped_column(JSON)


class Skill(Row):
    __tablename__ = "skills"
    name: Mapped[str] = mapped_column(unique=True)


class VacancySkill(Row):
    __tablename__ = "vacancy_skills"
    job_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), index=True)
    requirement: Mapped[str]
    __table_args__ = (UniqueConstraint("job_id", "skill_id", "requirement"),)
