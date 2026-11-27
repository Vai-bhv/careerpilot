import hashlib
import io
import re
from difflib import SequenceMatcher
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.table import Table
from pypdf import PdfReader
from sqlalchemy import select

from app.models import Citation, Evidence, Template
from app.repo import Problem, audit
from app.schemas import VARIANTS, EvidenceData, safe_url
from app.services.skills import norm, skills

MAX_UPLOAD = 8 * 1024 * 1024
SECTIONS = {
    "summary": ["professional summary", "summary", "profile", "profil"],
    "employment": [
        "professional experience",
        "work experience",
        "experience",
        "employment history",
        "pracovni zkusenosti",
    ],
    "project": ["projects", "portfolio projects", "projekty"],
    "skill": ["technical skills", "skills", "dovednosti"],
    "education": ["education", "vzdelani"],
    "certification": ["certifications", "certifikace"],
    "language": ["languages", "jazyky"],
}


def valid_link(values):
    for value in values:
        try:
            if safe_url(value):
                return value
        except ValueError:
            continue
    return ""


def extract(data, suffix):
    if not 0 < len(data) <= MAX_UPLOAD:
        raise Problem("Template must be between 1 byte and 8 MiB")
    try:
        if suffix == ".docx":
            with ZipFile(io.BytesIO(data)) as archive:
                if sum(i.file_size for i in archive.infolist()) > MAX_UPLOAD * 5:
                    raise Problem("Expanded template exceeds the import limit")
            doc = Document(io.BytesIO(data))
            rows = []
            for block in doc.iter_inner_content():
                paragraphs = (
                    [p for r in block.rows for c in r.cells for p in c.paragraphs]
                    if isinstance(block, Table)
                    else [block]
                )
                for p in paragraphs:
                    if p.text.strip():
                        rows.append((p.text.strip(), valid_link(h.url for h in p.hyperlinks)))
            return rows
        if suffix == ".pdf":
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted or len(reader.pages) > 25:
                raise Problem("Use an unlocked CV of up to 25 pages")
            rows = []
            for page in reader.pages:
                for line in (page.extract_text() or "").splitlines():
                    if line.strip():
                        rows.append((line.strip(), ""))
                for ref in page.get("/Annots", []):
                    target = ref.get_object().get("/A", {}).get("/URI")
                    if target and valid_link([target]):
                        rows.append((target, target))
            return rows
    except Problem:
        raise
    except Exception:  # noqa: BLE001 - parser libraries expose multiple archive/XML exceptions
        raise Problem("The template could not be parsed") from None
    raise Problem("Upload a DOCX or text-based PDF file")


def variant_for(path):
    name = norm(Path(path).stem.replace("_", " ").replace("-", " "))
    return next((v for v in VARIANTS if norm(v) in name), None)


def candidates(rows):
    section, owner = "identity", "Candidate"
    for index, (line, link) in enumerate(rows):
        heading = next(
            (k for k, aliases in SECTIONS.items() if norm(line).strip(":") in aliases), None
        )
        if heading:
            section, owner = heading, "Candidate"
            continue
        bullet = line.startswith(("•", "▪", "-", "●"))
        claim = line.lstrip("•▪● ").strip()
        kind = section
        if section == "identity":
            kind = (
                "identity"
                if index == 0
                else "contact"
                if ("@" in line or link or "|" in line)
                else "headline"
            )
        elif section == "employment":
            if not bullet and ("|" in line or re.search(r"\b(?:19|20)\d{2}\b", line)):
                owner = line.split("|")[0].strip()
            else:
                kind = "achievement"
        elif section == "project":
            if not bullet and (link or owner == "Candidate" or len(line) < 80):
                owner = line
            else:
                kind = "project_bullet"
        yield (
            index,
            EvidenceData(
                kind=kind,
                owner=owner,
                claim=claim,
                source=f"Template paragraph {index + 1}",
                technologies=skills(claim),
                link=link,
            ),
        )


def contradicts(a, b):
    if a.kind != b.kind or norm(a.owner) != norm(b.owner) or a.claim == b.claim:
        return False
    if a.kind in {"employment", "identity"}:
        return True
    numbers = lambda t: re.findall(r"\d+(?:[.,]\d+)?%?", t)
    return (
        numbers(a.claim) != numbers(b.claim)
        and SequenceMatcher(None, norm(a.claim), norm(b.claim)).ratio() >= 0.65
    )


def import_template(s, filename, data, variant):
    if variant not in VARIANTS:
        raise Problem("Choose one of the six CV variants")
    digest = hashlib.sha256(data).hexdigest()
    old = s.scalar(select(Template).where(Template.digest == digest, Template.variant == variant))
    if old:
        return old
    rows = extract(data, Path(filename).suffix.lower())
    if not rows:
        raise Problem("No readable paragraphs found. Use DOCX for scanned PDFs")
    template = Template(
        variant=variant, digest=digest, filename=Path(filename).name, content=data, paragraphs=rows
    )
    s.add(template)
    s.flush()
    existing = list(s.scalars(select(Evidence)))
    for idx, draft in candidates(rows):
        item = next(
            (
                r
                for r in existing
                if (r.kind, r.owner, r.claim, r.link)
                == (draft.kind, draft.owner, draft.claim, draft.link)
            ),
            None,
        )
        if item is None:
            item = Evidence(**draft.model_dump())
            item.source = f"Template {template.id}, paragraph {idx + 1}"
            conflicts = [r for r in existing if contradicts(r, item) and r.status != "not_approved"]
            item.conflict = bool(conflicts)
            for r in conflicts:
                r.conflict = True
            s.add(item)
            s.flush()
            existing.append(item)
        s.add(Citation(template_id=template.id, evidence_id=item.id, paragraph=idx))
    from app.services.matching import refresh_evaluations

    refresh_evaluations(s)
    audit(s, "template.import", template.id, variant=variant, paragraphs=len(rows))
    return template


def review(s, row, data):
    peers = list(s.scalars(select(Evidence).where(Evidence.kind == data.kind)))
    usable = data.status in {"user_confirmed", "source_supported"} and data.external
    if usable and any(
        other.id != row.id and contradicts(other, data) and other.status != "not_approved"
        for other in peers
    ):
        raise Problem(
            "Resolve conflicting source claims by marking the alternate versions not_approved first",
            409,
        )
    before = {k: getattr(row, k) for k in EvidenceData.model_fields}
    for k, v in data.model_dump().items():
        setattr(row, k, v)
    row.conflict = False if usable or data.status == "not_approved" else row.conflict
    from app.services.matching import refresh_evaluations

    refresh_evaluations(s)
    audit(s, "evidence.review", row.id, previous=before, reviewed=data.model_dump())
    return row
