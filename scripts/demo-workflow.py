"""Exercise the human workflow with fictional approvals in a fresh database."""

import json
import os
import tempfile
from pathlib import Path

from sqlalchemy import select

from app.cli import initialize
from app.db import transaction
from app.demo import seed_session
from app.models import Job
from app.schemas import Confirm, Generate, Tracking
from app.services.documents import approve, generate, validate
from app.services.tracking import confirm, track


def main():
    os.umask(0o077)
    base = Path("private/demo-exports").resolve()
    base.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="sample-", dir=base))
    os.environ["DATABASE_URL"] = f"sqlite:///{run}/demo.sqlite3"
    os.environ["CAREERPILOT_PRIVATE"] = str(run)
    initialize()
    with transaction() as s:
        seed_session(s)
        job = s.scalar(select(Job).where(Job.title == "Power BI Developer"))
        track(s, job, Tracking(status="shortlisted"))
        cv = generate(s, job, Generate())
        letter = generate(s, job, Generate(kind="cover_letter"))
        assert not validate(s, cv)
        approve(s, cv)
        approve(s, letter)
        application = confirm(
            s,
            job,
            Confirm(
                cv_id=cv.id, letter_id=letter.id, confirmed=True, method="fictional walkthrough"
            ),
        )
        (run / "sample.docx").write_bytes(cv.docx)
        (run / "sample.pdf").write_bytes(cv.pdf)
        (run / "sample.txt").write_text(cv.plain + "\n")
        (run / "sample.json").write_text(json.dumps(cv.snapshot, indent=2))
        print(
            f"Fictional application #{application.id}, CV #{cv.id}, cover letter #{letter.id}; files in {run}"
        )


if __name__ == "__main__":
    main()
