"""Restricted local Thunderbird import bridge."""

import json
import os
import secrets
import tempfile
from email.message import EmailMessage
from pathlib import Path

from pydantic import Field, ValidationError, field_validator

from app.config import private_root
from app.integrations.mail import ingest_message
from app.repo import Problem
from app.schemas import Input

MAX_REQUEST = 256_000


class ThunderbirdMessage(Input):
    message_id: str = Field(min_length=1, max_length=998)
    subject: str = Field(max_length=500)
    sender: str = Field(max_length=1000)
    body: str = Field(max_length=40_000)
    html: bool = False

    @field_validator("message_id", "subject", "sender")
    @classmethod
    def single_line(cls, value):
        if any(ord(char) < 32 for char in value):
            raise ValueError("Invalid mail header")
        return value


def token_path():
    return private_root() / "thunderbird.token"


def pair(action):
    path = token_path()
    if action == "revoke":
        path.unlink(missing_ok=True)
        return
    value = secrets.token_urlsafe(40)
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", delete=False) as temporary:
        temporary.write(value)
    os.replace(Path(temporary.name), path)
    print(value)


def authorize(header, origin):
    if origin and not origin.startswith("moz-extension://"):
        raise Problem("Thunderbird extension origin required", 403)
    try:
        expected = token_path().read_bytes().strip()
    except FileNotFoundError:
        expected = b""
    if not expected or not secrets.compare_digest(header.encode(), b"Bearer " + expected):
        raise Problem("Pair Thunderbird with this workspace", 401)


def import_payload(s, payload):
    try:
        message = ThunderbirdMessage.model_validate(json.loads(payload))
    except (ValueError, ValidationError):
        raise Problem("Invalid Thunderbird message") from None
    mail = EmailMessage()
    mail["Message-ID"] = message.message_id
    mail["Subject"] = message.subject
    mail["From"] = message.sender
    mail.set_content(message.body, subtype="html" if message.html else "plain")
    item = ingest_message(s, mail.as_bytes())
    return {"id": item.id, "category": item.category}
