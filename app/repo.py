from datetime import UTC, datetime

from sqlalchemy import select

from app.models import Application, Audit, Evidence, Profile


class Problem(ValueError):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


def get(s, model, key, *, lock=False):
    obj = s.get(model, key, with_for_update=lock)
    if obj is None:
        raise Problem(f"{model.__name__} not found", 404)
    return obj


def profile(s):
    return get(s, Profile, 1)


def audit(s, action, entity, **details):
    s.add(Audit(action=action, entity=str(entity), details=details))


def approved(s):
    return list(
        s.scalars(
            select(Evidence)
            .where(
                Evidence.external.is_(True),
                Evidence.conflict.is_(False),
                Evidence.status.in_(["user_confirmed", "source_supported"]),
            )
            .order_by(Evidence.id)
        )
    )


def public(row, omit=()):
    result = {
        col.key: getattr(row, col.key) for col in row.__table__.columns if col.key not in omit
    }
    # SQLite returns naive datetimes for UTC values written by our clock.
    return {
        k: v.replace(tzinfo=UTC) if isinstance(v, datetime) and v.tzinfo is None else v
        for k, v in result.items()
    }


def set_stage(s, job, stage):
    previous = job.status
    job.status = stage
    row = s.scalar(select(Application).where(Application.job_id == job.id))
    if row:
        row.status = stage
    audit(s, "vacancy.stage", f"job/{job.id}", previous=previous, status=stage)
