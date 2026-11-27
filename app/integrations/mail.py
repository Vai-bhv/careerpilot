import hashlib
import imaplib
import os
import re
import ssl
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr

from bs4 import BeautifulSoup
from sqlalchemy import select

from app.integrations.boards import state
from app.models import Mail
from app.repo import Problem, audit
from app.schemas import safe_url
from app.services.skills import norm

PATTERNS = {
    "rejection": r"unfortunately|not moving forward|other candidates|zamita|neuspes|nepostup",
    "interview": r"interview invitation|invite.{0,35}interview|schedule.{0,35}interview|pozvan.{0,15}pohovor",
    "confirmation": r"application (?:has been )?received|thank you for (?:applying|your application)|prijali jsme.{0,25}(?:zadost|zivotopis)",
    "job_alert": r"job alert|new jobs|new vacancies|nove nabidky|nabidky prace",
    "recruiter_reply": r"recruiter|recruitment team|talent acquisition|personalista",
}


def parse_mail(raw):
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    subject = str(msg.get("subject", ""))[:500]
    chunks, urls = [], []
    for part in msg.walk():
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        if part.get_content_type() not in {"text/plain", "text/html"}:
            continue
        value = part.get_content()
        if part.get_content_type() == "text/html":
            soup = BeautifulSoup(value, "html.parser")
            for tag in soup(["script", "style"]):
                tag.decompose()
            urls.extend(a["href"] for a in soup.find_all("a", href=True))
            value = soup.get_text(" ", strip=True)
        chunks.append(value)
    body = " ".join(" ".join(chunks).split())
    urls += re.findall(r'https?://[^\s<>"\)]+', body)
    links = []
    for u in urls:
        try:
            clean = safe_url(u.rstrip(".,"))
            if clean and clean not in links:
                links.append(clean)
        except ValueError:
            pass
    hits = [k for k, p in PATTERNS.items() if re.search(p, norm(subject + " " + body))]
    primary = [c for c in hits if c != "recruiter_reply"]
    category = primary[0] if len(primary) == 1 else hits[0] if len(hits) == 1 else "review"
    key = str(msg.get("Message-ID", "")).strip() or hashlib.sha256(raw).hexdigest()
    return {
        "message_key": hashlib.sha256(key.encode()).hexdigest(),
        "subject": subject,
        "summary": body[:1200],
        "links": links[:30],
        "category": category,
        "confidence": 0.9 if category != "review" else 0.35,
    }


def ingest_message(s, raw):
    data = parse_mail(raw)
    item = s.scalar(select(Mail).where(Mail.message_key == data["message_key"]))
    if not item:
        item = Mail(**data)
        s.add(item)
        s.flush()
        audit(s, "mail.classified", item.id, category=item.category)
    return item


def sync_yahoo(s, connector=imaplib.IMAP4_SSL):
    user, password = os.getenv("YAHOO_EMAIL"), os.getenv("YAHOO_APP_PASSWORD")
    if not user or not password:
        raise Problem("Configure Yahoo credentials in the local environment", 409)
    folder = os.getenv("YAHOO_FOLDER", "Jobs")
    sender = os.getenv("YAHOO_FROM", "").strip().casefold()
    rule = os.getenv("YAHOO_SEARCH", "UNSEEN").upper()
    if rule not in {"ALL", "SEEN", "UNSEEN", "FLAGGED"} or not re.fullmatch(
        r"[\w /.-]{1,150}", folder
    ):
        raise Problem("Invalid local IMAP settings")
    account = hashlib.sha256(f"{user}/{folder}/{sender}/{rule}".encode()).hexdigest()[:20]
    cursor = state(s, "yahoo/" + account)
    count = 0
    try:
        with connector(
            "imap.mail.yahoo.com", 993, ssl_context=ssl.create_default_context(), timeout=20
        ) as box:
            box.login(user, password)
            status, _ = box.select('"' + folder + '"', readonly=True)
            if status != "OK":
                raise OSError("select")
            validity = box.response("UIDVALIDITY")[1][0].decode()
            last = cursor.state.get("uid", 0) if cursor.state.get("validity") == validity else 0
            status, items = box.uid("SEARCH", None, "UID", f"{last + 1}:*", rule)
            if status != "OK":
                raise OSError("search")
            for uid in sorted(int(i) for i in items[0].split() if int(i) > last)[:100]:
                status, parts = box.uid("FETCH", str(uid), "(BODY.PEEK[]<0.1000000>)")
                if status != "OK":
                    raise OSError("fetch")
                raw = next((p[1] for p in parts if isinstance(p, tuple)), None)
                if raw is None:
                    raise OSError("empty fetch")
                msg = BytesParser(policy=policy.default).parsebytes(raw, headersonly=True)
                if not sender or parseaddr(msg.get("from", ""))[1].casefold() == sender:
                    try:
                        ingest_message(s, raw)
                        count += 1
                    except (ValueError, LookupError, UnicodeError):
                        audit(s, "mail.malformed", account, uid=uid)
                cursor.state = {"validity": validity, "uid": uid}
    except (imaplib.IMAP4.error, OSError, ValueError, AttributeError, IndexError) as exc:
        audit(s, "mail.sync_error", account, error=type(exc).__name__)
        return {"processed": count, "error": "Yahoo connection or mailbox read failed"}
    audit(s, "mail.sync", account, processed=count)
    return {"processed": count, "error": None}


def sync_mail(s):
    if os.getenv("CAREERPILOT_MAIL", "yahoo") == "mock":
        from pathlib import Path

        raw = (Path(__file__).resolve().parents[2] / "demo" / "mail-alert.txt").read_bytes()
        before = s.scalar(select(Mail.id).where(Mail.message_key == parse_mail(raw)["message_key"]))
        item = ingest_message(s, raw)
        return {"processed": int(before is None), "source": "mock", "id": item.id, "error": None}
    return sync_yahoo(s)


SUGGESTED = {
    "interview": "screening",
    "recruiter_reply": "recruiter_responded",
    "rejection": "rejected",
}
