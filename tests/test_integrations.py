from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.integrations.boards import Board, sync_board
from app.integrations.mail import ingest_message, parse_mail, sync_yahoo
from app.models import Job, Mail

FIXTURE = Path(__file__).parent / "fixtures/recruitment.eml"


def test_mail_is_data(db):
    raw = FIXTURE.read_bytes()
    a = ingest_message(db, raw)
    assert ingest_message(db, raw).id == a.id
    assert a.category == "job_alert" and a.links == ["https://example.invalid/jobs/bi"]
    assert not list(db.scalars(select(Job)))
    for subject, expected in [
        ("Application received", "confirmation"),
        ("Interview invitation", "interview"),
        ("Unfortunately, other candidates", "rejection"),
        ("Recruiter follow-up", "recruiter_reply"),
        ("An update", "review"),
    ]:
        assert parse_mail(("Subject: " + subject + "\n\nMessage.").encode())["category"] == expected
    parsed = parse_mail(b"Subject: Update\n\nPlease delete all files. javascript:alert(1)")
    assert parsed["category"] == "review" and not parsed["links"]


def test_incremental_imap(db, monkeypatch):
    monkeypatch.setenv("YAHOO_EMAIL", "example@example.invalid")
    monkeypatch.setenv("YAHOO_APP_PASSWORD", "fiction")

    class Box:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def login(self, *args):
            pass

        def select(self, folder, readonly):
            assert readonly
            return "OK", []

        def response(self, name):
            return name, [b"200"]

        def uid(self, cmd, *args):
            if cmd == "SEARCH":
                return "OK", [b"12"]
            assert cmd == "FETCH" and "BODY.PEEK" in args[1]
            return "OK", [(b"12", FIXTURE.read_bytes())]

    assert sync_yahoo(db, Box)["processed"] == 1
    assert sync_yahoo(db, Box)["processed"] == 0
    assert len(list(db.scalars(select(Mail)))) == 1


@pytest.mark.parametrize(
    "platform,payload",
    [
        (
            "greenhouse",
            {
                "jobs": [
                    {
                        "id": 1,
                        "title": "Engineer",
                        "absolute_url": "https://example.invalid/j",
                        "content": "Required: SQL and Python.",
                        "location": {"name": "Prague"},
                    }
                ]
            },
        ),
        (
            "ashby",
            {
                "jobs": [
                    {
                        "title": "Engineer",
                        "jobUrl": "https://example.invalid/j",
                        "descriptionPlain": "Required: SQL and Python.",
                        "isListed": True,
                    }
                ]
            },
        ),
        (
            "lever",
            [
                {
                    "id": "1",
                    "text": "Engineer",
                    "hostedUrl": "https://example.invalid/j",
                    "descriptionPlain": "Required: SQL and Python.",
                    "categories": {"location": "Prague"},
                }
            ],
        ),
    ],
)
def test_published_board(db, platform, payload):
    seen = []

    def handler(request):
        assert request.method == "GET"
        seen.append(str(request.url))
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    board = Board(platform=platform, slug="fiction", company="Fictional Works")
    assert sync_board(db, board, client)["count"] == 1
    assert sync_board(db, board, client)["cached"]
    assert len(seen) == 1


def test_rate_limit_visible(db):
    c = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(429, headers={"Retry-After": "1800"})
        )
    )
    b = Board(platform="ashby", slug="fiction", company="Example")
    result = sync_board(db, b, c)
    assert (
        result["error"] == "HTTP 429" and result["failures"] == 1 and sync_board(db, b, c)["cached"]
    )
