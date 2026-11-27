import hashlib
import io
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

from docx import Document as Word
from docx.enum.style import WD_STYLE_TYPE
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor
from pypdf import PdfReader
from sqlalchemy import select

from app.models import Citation, Document, Template
from app.repo import Problem, approved, audit, get
from app.services.matching import match

SECTIONS = {
    "identity": "",
    "contact": "",
    "summary": "Profile",
    "employment": "Experience",
    "achievement": "Experience",
    "project": "Projects",
    "project_bullet": "Projects",
    "skill": "Skills",
    "education": "Education",
    "certification": "Certifications",
    "language": "Languages",
}
BULLETS = {"achievement", "project_bullet"}
PARENT = {"achievement": "employment", "project_bullet": "project"}
HOURS = re.compile(
    r"(?:[,;]?\s*\(?\b\d+(?:[–-]\d+)?\s*(?:h(?:rs)?|hours?)\s*(?:/|per |a )\s*(?:week|wk)\b\)?)",
    re.IGNORECASE,
)


def line(e):
    return {
        "id": e.id,
        "kind": e.kind,
        "owner": e.owner,
        "text": HOURS.sub("", e.claim).strip(),
        "link": e.link,
    }


def select_lines(s, job, options):
    result = match(s, job)
    template = s.scalar(
        select(Template).where(Template.variant == result["variant"]).order_by(Template.id.desc())
    )
    local = (
        set(s.scalars(select(Citation.evidence_id).where(Citation.template_id == template.id)))
        if template
        else set()
    )
    ranks = {key: len(result["evidence_ids"]) - i for i, key in enumerate(result["evidence_ids"])}
    evidence = [e for e in approved(s) if e.id not in options.exclude and e.kind in SECTIONS]

    def include_metric(e):
        if (
            e.kind != "project_bullet"
            or not re.search(r"accuracy|f1.score|roc.auc|precision|recall", e.claim, re.IGNORECASE)
            or not re.search(r"\d", e.claim)
        ):
            return True
        # An evaluation claim must identify its data and its evaluation protocol in approved text.
        has_data = re.search(
            r"dataset|data set|corpus|benchmark|samples|records", e.claim, re.IGNORECASE
        )
        has_method = re.search(
            r"cross.validation|held.out|holdout|test set|test split|out.of.sample",
            e.claim,
            re.IGNORECASE,
        )
        return result["variant"] == "AI Engineering" and has_data and has_method

    evidence = [e for e in evidence if include_metric(e)]
    evidence.sort(key=lambda e: (-ranks.get(e.id, 0), e.id not in local, e.id))
    groups = defaultdict(list)
    for e in evidence:
        groups[e.kind].append(e)
    if options.kind != "cv":
        relevant = [e for e in evidence if e.kind in BULLETS and e.id in ranks]
        if not relevant:
            raise Problem(
                "Approve at least one vacancy-relevant achievement or project bullet first", 409
            )
        return [line(e) for e in relevant[: 1 if options.length == "brief" else 2]], template
    if not groups["identity"]:
        raise Problem("Approve an identity claim before generating a CV", 409)
    selected = groups["identity"][:1] + groups["contact"][:1] + groups["summary"][:1]
    for parent, child in [("employment", "achievement"), ("project", "project_bullet")]:
        seen = set()
        for header in groups[parent]:
            if header.owner in seen:
                continue
            seen.add(header.owner)
            selected.append(header)
            selected.extend([e for e in groups[child] if e.owner == header.owner][:3])
    for kind in ["skill", "education", "certification", "language"]:
        selected.extend(groups[kind][:3])
    if not any(e.kind in BULLETS for e in selected):
        raise Problem(
            "Approve an employment or project header and at least one bullet with the same owner",
            409,
        )
    return [line(e) for e in selected], template


def validate_lines(s, lines, kind="cv"):
    registry = {e.id: e for e in approved(s)}
    active = {}
    errors = []
    for entry in lines:
        source = registry.get(entry.get("id"))
        if not source or line(source) != entry:
            errors.append(f"Evidence {entry.get('id')} has changed or lacks disclosure approval")
            continue
        if (
            kind == "cv"
            and source.kind in PARENT
            and active.get(PARENT[source.kind]) != source.owner
        ):
            errors.append(f"Evidence {source.id} lacks its approved owner header")
        active[source.kind] = source.owner
    return errors


def rendered(snapshot):
    lines = snapshot["claims"]
    if snapshot["kind"] == "cv":
        previous = None
        rows = []
        for entry in lines:
            section = SECTIONS[entry["kind"]]
            if section and previous != section:
                rows.append(("section", section, ""))
            previous = section
            rows.append((entry["kind"], entry["text"], entry["link"]))
        return rows
    cs = snapshot["language"] == "cs"
    target = f"{snapshot['title']} ({snapshot['company']})"
    greetings = (
        ("Dobrý den," if cs else "Dear hiring team,")
        if snapshot["tone"] == "formal"
        else ("Dobrý den," if cs else "Hello,")
    )
    intros = {
        "cover_letter": ("Rád/a bych se ucházel/a o pozici", "I would like to apply for"),
        "motivation": ("Zaujala mě pozice", "I am interested in"),
        "recruiter_message": ("Mám zájem o pozici", "I am interested in discussing"),
        "email_application": ("Posílám přihlášku na pozici", "Please consider my application for"),
        "follow_up": (
            "Chtěl/a bych se informovat o pozici",
            "I wanted to ask about next steps for",
        ),
        "availability": (
            "Děkuji za možnost pohovoru na pozici",
            "Thank you for discussing an interview for",
        ),
    }
    intro = intros[snapshot["kind"]][0 if cs else 1]
    rows = [("text", greetings, ""), ("text", f"{intro} {target}.", "")]
    for e in lines:
        rows.append(("text", f"{e['owner']} — {e['text']}", e["link"]))
    closing = (
        ("Prosím o navržení termínu." if cs else "Please suggest a time to meet.")
        if snapshot["kind"] == "availability"
        else ("Děkuji za zvážení." if cs else "Thank you for your consideration.")
    )
    return rows + [("text", closing, "")]


def plain_text(snapshot):
    return "\n".join(
        ("• " if kind in BULLETS else "") + t + (f" ({link})" if link else "")
        for kind, t, link in rendered(snapshot)
    )


def hyperlink(paragraph, text, url):
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True))
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "124B65")
    props.append(color)
    run.append(props)
    t = OxmlElement("w:t")
    t.text = text
    run.append(t)
    link.append(run)
    paragraph._p.append(link)


def word_bytes(snapshot):
    word = Word()
    section = word.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    section.left_margin, section.right_margin = Mm(17), Mm(17)
    section.top_margin, section.bottom_margin = Mm(13), Mm(13)
    normal = word.styles["Normal"]
    normal.font.name = "Liberation Sans"
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(2.5)
    normal.paragraph_format.line_spacing = 1.04
    for key, size, color in [
        ("Section", 12, "124B65"),
        ("Name", 18, "162A36"),
        ("Header", 10.5, "162A36"),
    ]:
        st = word.styles.add_style("CV " + key, WD_STYLE_TYPE.PARAGRAPH)
        st.base_style = normal
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = RGBColor.from_string(color)
        st.paragraph_format.space_before = Pt(4)
        st.paragraph_format.keep_with_next = True
    styles = {
        "section": "CV Section",
        "identity": "CV Name",
        "employment": "CV Header",
        "project": "CV Header",
    }
    for kind, text, link in rendered(snapshot):
        p = word.add_paragraph(style=styles.get(kind, "Normal"))
        if kind in BULLETS:
            p.paragraph_format.left_indent = Mm(3)
            p.add_run("• ")
        if link:
            hyperlink(p, text, link)
        else:
            p.add_run(text)
    out = io.BytesIO()
    word.save(out)
    return out.getvalue()


def convert(data):
    executable = shutil.which("soffice")
    if not executable:
        raise Problem("Install LibreOffice Writer to export and verify a one-page PDF", 503)
    with tempfile.TemporaryDirectory(prefix="careerpilot-render-") as directory:
        root = Path(directory)
        path = root / "cv.docx"
        path.write_bytes(data)
        try:
            proc = subprocess.run(
                [
                    executable,
                    f"-env:UserInstallation={(root / 'office').as_uri()}",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(root),
                    str(path),
                ],
                capture_output=True,
                timeout=40,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise Problem("PDF conversion timed out", 503) from None
        if proc.returncode or not (root / "cv.pdf").is_file():
            raise Problem("LibreOffice could not convert the document", 503)
        return (root / "cv.pdf").read_bytes()


def pdf_info(data):
    reader = PdfReader(io.BytesIO(data))
    links = {
        a.get_object().get("/A", {}).get("/URI") for p in reader.pages for a in p.get("/Annots", [])
    }
    return len(reader.pages), links


def generate(s, job, options):
    claims, template = select_lines(s, job, options)
    if options.base_version is not None:
        base = get(s, Document, options.base_version)
        if base.job_id != job.id or base.kind != "cv":
            raise Problem("Select a CV version of this vacancy", 409)
        frozen = base.snapshot["claims"]
        # Rebuild the requested section only. Every retained line must still validate.
        claims = [
            e
            for section in dict.fromkeys(SECTIONS.values())
            for e in (claims if section == options.section else frozen)
            if SECTIONS[e["kind"]] == section
        ]
        errors = validate_lines(s, claims)
        if errors:
            raise Problem(
                "Other sections contain outdated evidence. Generate a new full draft", 409
            )
    snapshot = {
        "base_version": options.base_version,
        "kind": options.kind,
        "title": job.title,
        "company": job.company,
        "template_id": template.id if template else None,
        "variant": match(s, job)["variant"],
        "claims": claims,
        "language": options.language,
        "tone": options.tone,
        "version": "extractive-v1",
    }
    docx = pdf = None
    if options.kind == "cv":
        while True:
            docx = word_bytes(snapshot)
            pdf = convert(docx)
            pages, links = pdf_info(pdf)
            if pages == 1:
                break
            removable = [
                e
                for e in reversed(claims)
                if e["kind"] in BULLETS
                and sum(c["kind"] == e["kind"] and c["owner"] == e["owner"] for c in claims) > 1
            ]
            removable += [
                e
                for e in reversed(claims)
                if e["kind"] in {"summary", "language", "certification", "skill"}
            ]
            if options.section:
                removable = [e for e in removable if SECTIONS[e["kind"]] == options.section]
            if not removable:
                raise Problem(
                    "Approved content exceeds one A4 page. Shorten evidence or exclude lower-priority lines",
                    409,
                )
            claims.remove(removable[0])
        if not {e["link"] for e in claims if e["link"]}.issubset(links):
            raise Problem("A project or contact hyperlink did not survive PDF conversion", 409)
        snapshot["pages"] = pages
        snapshot["pdf_sha256"] = hashlib.sha256(pdf).hexdigest()
        snapshot["docx_sha256"] = hashlib.sha256(docx).hexdigest()
    errors = validate_lines(s, claims, options.kind)
    if errors:
        raise Problem("; ".join(errors), 409)
    doc = Document(
        job_id=job.id,
        kind=options.kind,
        snapshot=snapshot,
        plain=plain_text(snapshot),
        docx=docx,
        pdf=pdf,
    )
    s.add(doc)
    s.flush()
    audit(
        s,
        "document.generate",
        doc.id,
        job=job.id,
        policy=snapshot["version"],
        options=options.model_dump(),
        evidence=[c["id"] for c in claims],
    )
    if options.kind == "cv" and job.status in {
        "discovered",
        "evaluated",
        "shortlisted",
        "cv_generated",
    }:
        from app.repo import set_stage

        set_stage(s, job, "awaiting_approval")
    return doc


def validate(s, doc):
    errors = validate_lines(s, doc.snapshot["claims"], doc.kind)
    if doc.plain != plain_text(doc.snapshot):
        errors.append("Document text differs from validated claims")
    if doc.kind == "cv":
        for fmt in ["pdf", "docx"]:
            if hashlib.sha256(getattr(doc, fmt) or b"").hexdigest() != doc.snapshot.get(
                fmt + "_sha256"
            ):
                errors.append(f"{fmt.upper()} digest differs from the generated version")
    return errors


def approve(s, doc):
    errors = validate(s, doc)
    if errors:
        raise Problem("; ".join(errors), 409)
    doc.approved = True
    audit(s, "document.approve", doc.id, job=doc.job_id)
    return doc
