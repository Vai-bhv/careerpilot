import hashlib
import os
import re
from datetime import timedelta
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import delete, func, or_, select, update

from app.db import now
from app.models import Job, Match, Profile, Skill, SourceRecord, VacancySkill
from app.repo import Problem, audit, public
from app.schemas import JobData
from app.services.skills import norm, skills

PREFERRED = r"nice.to.have|preferred|bonus|advantage|additional skills|stand out|vyhodou|vitame"
REQUIRED = r"required|requirements|must.have|mandatory|you.need|qualifications|what are we looking for|what you.ll bring|what you bring|pozadujeme|pozadavky|nutna|nezbytne"
RESP = r"responsibilities|what you.ll do|what you will do|what will you do|napln prace|odpovednosti"
BENEFITS = r"benefits|benefity|nabizime|we offer"


def canonical(url):
    if not url:
        return None
    u = urlsplit(url)
    host = u.netloc.lower()
    if (u.scheme == "https" and u.port == 443) or (u.scheme == "http" and u.port == 80):
        host = host.rsplit(":", 1)[0]
    query = [
        (k, v)
        for k, v in parse_qsl(u.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in {"gh_src", "fbclid", "trk"}
    ]
    return urlunsplit(
        (u.scheme.lower(), host, u.path.rstrip("/") or "/", urlencode(sorted(query)), "")
    )


def structured(data):
    fields = data.model_dump(
        mode="json",
        exclude={
            "title",
            "company",
            "location",
            "url",
            "apply_url",
            "description",
            "source",
            "external_id",
        },
    )
    sections = {"required": [], "preferred": [], "responsibilities": [], "benefits": []}
    state = None
    language_hits = []
    # A heading persists across bullet lines. Clauses can introduce an inline preferred list.
    for original in re.split(
        r"[\n;]|(?<=[.])\s+|,\s*(?=(?:preferred|nice.to.have|výhodou|bonus))",
        data.description,
        flags=re.IGNORECASE,
    ):
        if not original.strip():
            continue
        lower = norm(original)
        if re.match(
            r"^(?:about (?:us|the company)|work mode|our team|reports to|o spolecnosti)\b", lower
        ):
            state = None
        for key, pattern in [
            ("benefits", BENEFITS),
            ("responsibilities", RESP),
            ("preferred", PREFERRED),
            ("required", REQUIRED),
        ]:
            if re.search(pattern, lower):
                state = key
                break
        if state in ("required", "preferred"):
            sections[state].extend(skills(original))
            if state == "required":
                for label, words in [
                    ("Czech", r"\bczech\b|cestin"),
                    ("English", r"\benglish\b|anglictin"),
                    ("German", r"\bgerman\b|nemcin"),
                ]:
                    if re.search(words, lower) and not re.search("czech republic|czechia", lower):
                        language_hits.append(label)
            if fields["experience"] is None and re.search(r"\d\+?\s*(?:years|let|rok)", lower):
                fields["experience"] = original.strip()[:500]
            if fields["education"] is None and re.search(
                "degree|bachelor|master.s|vysokoskol", lower
            ):
                fields["education"] = original.strip()[:500]
        if state in ("benefits", "responsibilities"):
            sections[state].append(original.strip())
    for key, items in sections.items():
        if fields[key] is None:
            fields[key] = list(dict.fromkeys(items)) or None
    if fields["languages"] is None:
        fields["languages"] = list(dict.fromkeys(language_hits)) or None
    lower = norm(data.description)
    for key, choices in {
        "arrangement": {
            "hybrid": "hybrid",
            "remote": "fully remote|plne na dalku",
            "onsite": "on.site|on.site only",
        },
        "employment_type": {
            "full-time": "full.time|plny uvazek",
            "part-time": "part.time|castecny uvazek",
        },
    }.items():
        matches = [v for v, pat in choices.items() if re.search(pat, lower)]
        if fields[key] is None and len(matches) == 1:
            fields[key] = matches[0]
    # Keep currency and period separate. Never infer currency from location.
    salary = re.search(
        r"(?:salary|plat|mzda|odmena)\s*[:=]?\s*(\d{1,3}(?:[ ,]\d{3})+|\d{4,})\s*[-–—]\s*(\d{1,3}(?:[ ,]\d{3})+|\d{4,})\s*(czk|kc|eur|usd)\b",
        lower,
    )
    if salary and fields["salary_min"] is None and fields["salary_max"] is None:
        low, high = (int(re.sub(r"[ ,]", "", n)) for n in salary.groups()[:2])
        if low <= high:
            fields.update(
                salary_min=low,
                salary_max=high,
                currency={"kc": "CZK"}.get(salary[3], salary[3].upper()),
            )
            tail = lower[salary.end() : salary.end() + 30]
            if re.match(r"\s*(?:/|per |a )?\s*(?:month|mesic)", tail):
                fields["period"] = "month"
            elif re.match(r"\s*(?:/|per |a )?\s*(?:year|rok|annual)", tail):
                fields["period"] = "year"
    if fields["work_authorisation"] is None and re.search(
        r"(?:must (?:already )?(?:be authori[sz]ed|have (?:the )?right) to work in (?:the )?czech|platne pracovni povoleni v cr)",
        lower,
    ):
        fields["work_authorisation"] = "authorisation_required"
    fields["confidence"] = "explicit_fields_and_rules"
    return fields


def ingest(s, data: JobData):
    # Serialize identity decisions before reading alternative source records.
    s.execute(update(Profile).where(Profile.id == 1).values(id=1))
    url = canonical(data.url)
    fp = hashlib.sha256(norm(data.description).encode()).hexdigest()
    identity = (
        data.external_id
        or url
        or hashlib.sha256(
            repr((norm(data.company), norm(data.title), norm(data.location or ""), fp)).encode()
        ).hexdigest()
    )
    src = s.scalar(
        select(SourceRecord).where(
            SourceRecord.source == data.source, SourceRecord.identity == identity
        )
    )
    job = s.get(Job, src.job_id) if src else None
    if not job and url:
        job = s.scalar(select(Job).where(Job.url == url))
    peers = list(
        s.scalars(
            select(Job).where(
                func.lower(Job.company) == data.company.lower(),
                func.lower(Job.title) == data.title.lower(),
            )
        )
    )
    same_source = set(
        s.scalars(select(SourceRecord.job_id).where(SourceRecord.source == data.source))
    )
    if not job:
        job = next(
            (
                p
                for p in peers
                if p.fingerprint == fp
                and norm(p.location or "") == norm(data.location or "")
                and not (p.id in same_source and (data.external_id or (url and p.url != url)))
            ),
            None,
        )
    fields = structured(data)
    update_skills = job is None or src is not None
    if not job:
        threshold = float(os.getenv("CAREERPILOT_DUPLICATE_SIMILARITY", ".78"))
        fields["possible_duplicates"] = [
            p.id
            for p in peers
            if SequenceMatcher(
                None, norm(p.description)[:4000], norm(data.description)[:4000], autojunk=True
            ).ratio()
            >= threshold
        ]
        job = Job(
            title=data.title,
            company=data.company,
            location=data.location,
            url=url,
            apply_url=data.apply_url or url,
            description=data.description,
            fingerprint=fp,
            fields=fields,
        )
        s.add(job)
        s.flush()
    elif src:
        fields["possible_duplicates"] = job.fields.get("possible_duplicates", [])
        job.fields, job.description, job.fingerprint = fields, data.description, fp
        job.title, job.company, job.location = data.title, data.company, data.location
        job.url, job.apply_url = url or job.url, data.apply_url or url or job.apply_url
    if update_skills:
        s.execute(delete(VacancySkill).where(VacancySkill.job_id == job.id))
        for requirement in ("required", "preferred"):
            for name in dict.fromkeys(fields.get(requirement) or []):
                skill = s.scalar(select(Skill).where(Skill.name == name))
                if not skill:
                    skill = Skill(name=name)
                    s.add(skill)
                    s.flush()
                s.add(VacancySkill(job_id=job.id, skill_id=skill.id, requirement=requirement))
    job.checked = now()
    if not src:
        src = SourceRecord(source=data.source, identity=identity, job_id=job.id)
        s.add(src)
    src.payload = data.model_dump(mode="json")
    existing_match = s.scalar(select(Match).where(Match.job_id == job.id))
    if existing_match:
        from app.services.matching import match

        existing_match.result = match(s, job)
    audit(s, "job.ingest", job.id, source=data.source)
    return job


def find_jobs(
    s,
    q="",
    company="",
    location="",
    source="",
    status="",
    limit=50,
    offset=0,
    min_score=0,
    category=None,
    within_days=None,
):
    stmt = select(Job)
    if within_days:
        stmt = stmt.where(Job.checked >= now() - timedelta(days=within_days))
    if min_score or category:
        stmt = stmt.join(Match, Match.job_id == Job.id)
        if min_score:
            stmt = stmt.where(Match.result["score"].as_integer() >= min_score)
        if category:
            stmt = stmt.where(Match.result["variant"].as_string() == category)
    if q:
        if s.get_bind().dialect.name == "postgresql":
            stmt = stmt.where(
                func.to_tsvector(
                    "simple", Job.title + " " + Job.company + " " + Job.description
                ).op("@@")(func.plainto_tsquery("simple", q))
            )
        else:
            stmt = stmt.where(
                or_(
                    *(
                        col.icontains(q, autoescape=True)
                        for col in [Job.title, Job.company, Job.description]
                    )
                )
            )
    for col, value in [(Job.company, company), (Job.location, location)]:
        if value:
            stmt = stmt.where(col.icontains(value, autoescape=True))
    if status:
        stmt = stmt.where(Job.status == status)
    if source:
        stmt = stmt.where(
            Job.id.in_(select(SourceRecord.job_id).where(SourceRecord.source == source))
        )
    return [
        public(j)
        for j in s.scalars(
            stmt.order_by(Job.created.desc(), Job.id.desc()).limit(limit).offset(offset)
        )
    ]


def import_rows(s, records):
    if len(records) > 1000:
        raise Problem("Limit bulk imports to 1000 rows")
    result = []
    for i, record in enumerate(records, 1):
        try:
            with s.begin_nested():
                job = ingest(s, JobData.model_validate(record))
            result.append({"row": i, "id": job.id})
        except (ValueError, TypeError):
            audit(s, "ingest.invalid", i)
            result.append({"row": i, "error": "Malformed vacancy. Check fields and URLs."})
    return result
