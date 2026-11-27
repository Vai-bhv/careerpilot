from datetime import timedelta

from sqlalchemy import select

from app.db import now, transaction
from app.integrations.boards import state
from app.models import Audit
from app.scheduler import tick


def test_due_jobs_and_nonoverlap(workspace):
    with transaction() as s:
        state(s, "schedule/follow_ups").state = {"enabled": True, "interval_minutes": 60}
    tick()
    tick()
    with transaction() as s:
        runs = list(s.scalars(select(Audit).where(Audit.action == "schedule.run")))
        assert len(runs) == 1 and runs[0].details["result"] == {"due": 0}


def test_retention_preview_and_confirmation(db):
    from app.integrations.mail import ingest_message
    from app.services.privacy import expire_mail

    msg = ingest_message(db, b"Subject: Recruiter update\n\nRecruitment team.")
    msg.created = now() - timedelta(days=100)
    assert expire_mail(db, 90)["eligible"] == 1 and msg.summary
    expire_mail(db, 90, True)
    assert not msg.summary
