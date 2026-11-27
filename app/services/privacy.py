"""Retention is opt-in and only removes old, unlinked mailbox excerpts."""

from datetime import timedelta

from sqlalchemy import select

from app.db import now
from app.models import Mail
from app.repo import audit


def expire_mail(s, days, confirmed=False):
    cutoff = now() - timedelta(days=days)
    rows = list(
        s.scalars(
            select(Mail).where(Mail.created < cutoff, Mail.job_id.is_(None), Mail.summary != "")
        )
    )
    if confirmed:
        for row in rows:
            row.summary = ""
            row.subject = "Expired communication"
            row.links = []
        audit(s, "privacy.retention", "mail", count=len(rows), days=days)
    return {"eligible": len(rows), "applied": confirmed}
