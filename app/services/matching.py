from collections import Counter
from difflib import SequenceMatcher

from sqlalchemy import select

from app.models import Application, Job, Match
from app.repo import approved, profile
from app.schemas import Preferences
from app.services.skills import norm, skills

CUES = {
    "BI Engineering": ["power bi", "business intelligence", "bi engineer", "dax", "bi developer"],
    "Data Analytics": [
        "data analyst",
        "analytics specialist",
        "bi analyst",
        "reporting analyst",
        "excel",
        "business analyst",
    ],
    "Automation Engineering": [
        "automation",
        "power platform",
        "power automate",
        "power apps",
        "integration engineer",
    ],
    "Analytics Engineering": ["analytics engineer", "dbt", "data modeling", "snowflake"],
    "Data Engineering": ["data engineer", "etl", "airflow", "spark", "pipeline"],
    "AI Engineering": ["ai engineer", "machine learning", "pytorch", "tensorflow", "scikit-learn"],
}


def variant(job):
    title = norm(job.title)
    desc = norm(job.description)
    return max(CUES, key=lambda k: sum(5 * (c in title) + (c in desc) for c in CUES[k]))


def match(s, job):
    ev = approved(s)
    prefs = Preferences.model_validate(profile(s).preferences)
    f = job.fields
    inventory = {norm(t) for e in ev for t in e.technologies + skills(e.claim)}
    required, preferred = f.get("required") or [], f.get("preferred") or []
    matched = [t for t in required + preferred if norm(t) in inventory]
    missing = [t for t in required if norm(t) not in inventory]
    bonus = [t for t in preferred if norm(t) not in inventory]
    wanted = {norm(t) for t in required + preferred + skills(job.description)}

    def relevance(e):
        return len({norm(t) for t in e.technologies + skills(e.claim)} & wanted)

    ranked = sorted((e for e in ev if relevance(e)), key=lambda e: (-relevance(e), e.id))
    parts = {}
    if required:
        parts["required"] = (len(required) - len(missing)) / len(required)
    if preferred:
        parts["preferred"] = (len(preferred) - len(bonus)) / len(preferred)
    if prefs.target_roles:
        parts["role"] = max(
            1
            if norm(r) in norm(job.title)
            else SequenceMatcher(None, norm(r), norm(job.title)).ratio()
            for r in prefs.target_roles
        )
    if job.location and prefs.locations:
        parts["location"] = float(any(norm(p) in norm(job.location) for p in prefs.locations))
    for key, preference in [
        ("employment", prefs.employment_type),
        ("arrangement", prefs.arrangement),
    ]:
        actual = f.get("employment_type" if key == "employment" else key)
        if actual and preference:
            parts[key] = float(norm(preference) == norm(actual))
    if f.get("seniority") and prefs.seniorities:
        parts["seniority"] = float(norm(f["seniority"]) in [norm(v) for v in prefs.seniorities])
    if prefs.domains:
        parts["domain"] = float(any(norm(d) in norm(job.description) for d in prefs.domains))
    if wanted:
        parts["projects"] = float(any(e.kind.startswith("project") for e in ranked))
    if f.get("responsibilities"):
        words = set(norm(" ".join(f["responsibilities"])).split())
        parts["responsibilities"] = max(
            (
                len(words & set(norm(e.claim).split())) / max(1, len(words))
                for e in ev
                if e.kind == "achievement"
            ),
            default=0,
        )
    concerns = []
    if (
        prefs.minimum_salary is not None
        and f.get("salary_max") is not None
        and prefs.salary_currency
        and prefs.salary_period
        and f.get("currency") == prefs.salary_currency
        and f.get("period") == prefs.salary_period
    ):
        parts["salary"] = float(f["salary_max"] >= prefs.minimum_salary)
    review = []
    conflicts = []
    if f.get("languages"):
        if prefs.languages is None:
            review.append("Confirm required language proficiency")
        elif not {norm(t) for t in f["languages"]}.issubset({norm(t) for t in prefs.languages}):
            review.append("Verify proficiency in each listed language")
    if f.get("work_authorisation"):
        if (
            prefs.work_authorisation == "not_authorised"
            and f["work_authorisation"] == "authorisation_required"
        ):
            conflicts.append("Confirmed work authorisation conflicts with the requirement")
        elif (
            prefs.work_authorisation != "authorised"
            or f["work_authorisation"] != "authorisation_required"
        ):
            review.append("Review the vacancy’s work authorisation requirement")
    elif prefs.work_authorisation is None:
        review.append("Work authorisation is unknown")
    if f.get("experience"):
        concerns.append("Check the stated experience requirement against official employment dates")
    total = sum(prefs.weights.get(k, 0) for k in parts)
    score = (
        round(100 * sum(v * prefs.weights.get(k, 0) for k, v in parts.items()) / total)
        if total
        else 0
    )
    band = (
        "strong"
        if score >= 80
        else "reasonable"
        if score >= 60
        else "stretch"
        if score >= 35
        else "poor"
    )
    if not required:
        concerns.append("Mandatory technical requirements need review")
    if not ev:
        concerns.append("No approved evidence is available")
    return {
        "score": score,
        "technical_score": round(100 * parts["required"]) if required else None,
        "eligibility": "conflict" if conflicts else "review" if review else "no_known_conflict",
        "fit": band,
        "recommendation": "poor"
        if conflicts
        else "clarify"
        if review or not ev or not required
        else band,
        "matched": sorted(set(matched)),
        "missing_required": missing,
        "missing_preferred": bonus,
        "achievements": [e.id for e in ranked if e.kind == "achievement"],
        "projects": [e.id for e in ranked if e.kind.startswith("project")],
        "variant": variant(job),
        "concerns": conflicts + review + concerns,
        "evidence_ids": [e.id for e in ranked],
        "components": {k: round(v, 3) for k, v in parts.items()},
        "explanation": f"{len(required) - len(missing)} of {len(required)} identified mandatory skills have approved evidence. Score uses available weighted factors.",
    }


def save_match(s, job):
    result = match(s, job)
    row = s.scalar(select(Match).where(Match.job_id == job.id))
    if row:
        row.result = result
    else:
        s.add(Match(job_id=job.id, result=result))
    if job.status == "discovered":
        job.status = "evaluated"
    return result


def gaps(s, shortlisted=False, role=""):
    counts, missing, strong = Counter(), Counter(), Counter()
    stmt = select(Job)
    if shortlisted:
        stmt = stmt.where(
            Job.id.in_(select(Application.job_id).where(Application.status == "shortlisted"))
        )
    if role:
        stmt = stmt.where(Job.title.icontains(role, autoescape=True))
    for job in s.scalars(stmt):
        result = match(s, job)
        counts.update(job.fields.get("required") or [])
        missing.update(result["missing_required"])
        if result["fit"] == "strong":
            strong.update(result["matched"])
    return {
        k: dict(v.most_common())
        for k, v in [("demand", counts), ("missing", missing), ("strong", strong)]
    }


def refresh_evaluations(s):
    for row, job in s.execute(select(Match, Job).join(Job, Job.id == Match.job_id)):
        row.result = match(s, job)
