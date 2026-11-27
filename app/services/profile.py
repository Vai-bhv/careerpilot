import re

from sqlalchemy import select

from app.models import Evidence
from app.repo import public


def structured_profile(s):
    sections = {
        "employment": [],
        "projects": [],
        "education": [],
        "skills": [],
        "certifications": [],
        "languages": [],
    }
    all_rows = list(s.scalars(select(Evidence).order_by(Evidence.id)))
    for e in all_rows:
        value = public(e)
        if e.kind == "employment":
            parts = [p.strip() for p in e.claim.split("|")]
            role = parts[1] if len(parts) > 1 else None
            dates = parts[-1] if len(parts) > 2 else None
            period = re.split(r"\s+[–—-]\s+", dates, maxsplit=1) if dates else []
            employment_type = re.search(
                r"part[- ]time|full[- ]time|contract|internship", role or "", re.IGNORECASE
            )
            value.update(
                official_title=role,
                employment_type=employment_type.group() if employment_type else None,
                start=period[0] if len(period) == 2 else None,
                end=period[1] if len(period) == 2 else None,
                date_text=dates,
            )
        section = {
            "employment": "employment",
            "project": "projects",
            "skill": "skills",
            "certification": "certifications",
            "education": "education",
            "language": "languages",
        }.get(e.kind)
        if section:
            if e.kind in {"employment", "project"}:
                child = "achievement" if e.kind == "employment" else "project_bullet"
                value["supporting_evidence"] = [
                    c.id for c in all_rows if c.kind == child and c.owner == e.owner
                ]
            sections[section].append(value)
    return sections
