import fcntl
import os
import signal
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from pydantic import Field
from sqlalchemy import select

from app.config import private_root
from app.db import now, transaction
from app.integrations.boards import Board, state, sync_board
from app.integrations.mail import sync_mail
from app.models import Integration, Job
from app.repo import audit
from app.schemas import Input
from app.services.matching import save_match
from app.services.tracking import statistics


class Schedule(Input):
    enabled: bool = False
    interval_minutes: int = Field(60, ge=5, le=10080)


TASKS = ("boards", "mail", "matching", "freshness", "follow_ups")


def perform(s, name):
    if name == "mail":
        return sync_mail(s)
    if name == "boards":
        rows = list(s.scalars(select(Integration)))
        return {
            "boards": [
                sync_board(s, Board.model_validate(r.state["board"]))
                for r in rows
                if "board" in r.state and r.state.get("enabled", True)
            ]
        }
    if name == "follow_ups":
        return {"due": statistics(s)["follow_ups"]}
    jobs = list(s.scalars(select(Job)))
    stale = 0
    for j in jobs:
        if name == "matching":
            save_match(s, j)
        if name == "freshness":
            expires = j.fields.get("expires")
            if (
                expires
                and expires < date.today().isoformat()
                and j.status
                in {"discovered", "evaluated", "shortlisted", "awaiting_approval", "ready_to_apply"}
            ):
                from app.repo import set_stage

                set_stage(s, j, "expired")
            if j.checked.date() < (now() - timedelta(days=30)).date():
                stale += 1
    return {"checked": len(jobs), "stale": stale}


def tick():
    from datetime import datetime

    for name in TASKS:
        with transaction() as s:
            cfg = state(s, "schedule/" + name)
            value = cfg.state
            if not value.get("enabled") or (
                value.get("next") and datetime.fromisoformat(value["next"]) > now()
            ):
                continue
            cfg.state = {
                **value,
                "next": (now() + timedelta(minutes=value["interval_minutes"])).isoformat(),
            }
        for attempt in (1, 2):
            try:
                with transaction() as s:
                    result = perform(s, name)
                    audit(s, "schedule.run", name, attempt=attempt, result=result)
                if result.get("error") and attempt == 1:
                    continue
                break
            except Exception as exc:  # noqa: BLE001 - isolate independently scheduled tasks
                with transaction() as s:
                    audit(s, "schedule.error", name, attempt=attempt, error=type(exc).__name__)


def run():
    lock = (private_root() / "worker.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Scheduler already running in this workspace")
    scheduler = BlockingScheduler(
        timezone=ZoneInfo(os.getenv("CAREERPILOT_TIMEZONE", "Europe/Prague"))
    )
    scheduler.add_job(
        tick,
        "interval",
        minutes=1,
        id="due-tasks",
        max_instances=1,
        coalesce=True,
        next_run_time=now(),
    )
    signal.signal(signal.SIGTERM, lambda *_: scheduler.shutdown(wait=True))
    try:
        scheduler.start()
    except KeyboardInterrupt:
        pass
    finally:
        lock.close()
