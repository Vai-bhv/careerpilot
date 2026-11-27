"""Employer-enabled public board reads. Manual URLs are never fetched."""

import html
import re
from datetime import UTC, datetime, timedelta
from typing import Literal

import httpx
from bs4 import BeautifulSoup
from pydantic import Field
from sqlalchemy import select

from app.db import now
from app.models import Integration
from app.repo import Problem, audit
from app.schemas import Input, JobData, Text
from app.services.jobs import ingest


class Board(Input):
    platform: Literal["greenhouse", "ashby", "lever", "lever-eu"]
    slug: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    company: Text


def state(s, name):
    row = s.scalar(select(Integration).where(Integration.name == name).with_for_update())
    if row is None:
        row = Integration(name=name, state={})
        s.add(row)
        s.flush()
    return row


def plain(value):
    return BeautifulSoup(html.unescape(value or ""), "html.parser").get_text("\n", strip=True)


class BoardAdapter:
    def __init__(self, board, client):
        self.board, self.client = board, client

    def records(self):
        b = self.board
        if b.platform == "greenhouse":
            response = self.client.get(
                f"https://boards-api.greenhouse.io/v1/boards/{b.slug}/jobs",
                params={"content": "true"},
            )
            response.raise_for_status()
            for job in response.json()["jobs"]:
                yield {
                    "external_id": str(job["id"]),
                    "title": job["title"],
                    "location": (job.get("location") or {}).get("name"),
                    "url": job["absolute_url"],
                    "description": plain(job.get("content")),
                }
        elif b.platform == "ashby":
            response = self.client.get(f"https://api.ashbyhq.com/posting-api/job-board/{b.slug}")
            response.raise_for_status()
            for job in response.json()["jobs"]:
                if job.get("isListed") is False:
                    continue
                yield {
                    "title": job["title"],
                    "location": job.get("location"),
                    "url": job["jobUrl"],
                    "apply_url": job.get("applyUrl"),
                    "description": job.get("descriptionPlain") or plain(job.get("descriptionHtml")),
                    "employment_type": job.get("employmentType"),
                    "arrangement": job.get("workplaceType"),
                    "published": (job.get("publishedAt") or "")[:10] or None,
                }
        else:
            host = "api.eu.lever.co" if b.platform == "lever-eu" else "api.lever.co"
            skip = 0
            while True:
                response = self.client.get(
                    f"https://{host}/v0/postings/{b.slug}",
                    params={"mode": "json", "limit": 100, "skip": skip},
                )
                response.raise_for_status()
                batch = response.json()
                for job in batch:
                    details = "\n".join(
                        [job.get("descriptionPlain", "")]
                        + [plain(r["text"] + "\n" + r["content"]) for r in job.get("lists", [])]
                        + [job.get("additionalPlain", "")]
                    )
                    yield {
                        "external_id": str(job["id"]),
                        "title": job["text"],
                        "location": job.get("categories", {}).get("location"),
                        "url": job["hostedUrl"],
                        "apply_url": job.get("applyUrl"),
                        "description": details,
                    }
                if len(batch) < 100:
                    break
                skip += 100
                if skip >= 2000:
                    raise Problem("Board exceeds the local page limit")
                import time

                time.sleep(1)


def sync_board(s, b, client=None):
    key = f"{b.platform}/{b.slug}"
    row = state(s, key)
    old = row.state
    current = now()
    if old.get("next_read") and datetime.fromisoformat(old["next_read"]) > current:
        return {**old, "cached": True}
    valid = invalid = 0
    retry_after = 300
    failure = None
    owned = client is None
    client = client or httpx.Client(timeout=15, follow_redirects=False)
    try:
        for raw in BoardAdapter(b, client).records():
            try:
                ingest(s, JobData.model_validate({**raw, "source": key, "company": b.company}))
                valid += 1
            except ValueError:
                invalid += 1
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        failure = type(exc).__name__
        if isinstance(exc, httpx.HTTPStatusError):
            failure = f"HTTP {exc.response.status_code}"
            wait = exc.response.headers.get("retry-after", "")
            if re.fullmatch(r"\d{1,8}", wait):
                retry_after = max(retry_after, int(wait))
            elif wait:
                from email.utils import parsedate_to_datetime

                try:
                    retry_after = max(
                        retry_after,
                        int(
                            (parsedate_to_datetime(wait).astimezone(UTC) - current).total_seconds()
                        ),
                    )
                except (TypeError, ValueError):
                    pass
    finally:
        if owned:
            client.close()
    row.state = {
        "board": b.model_dump(),
        "count": valid,
        "invalid": invalid,
        "error": failure,
        "attempt": current.isoformat(),
        "failures": (old.get("failures", 0) + 1 if failure else 0),
        "next_read": (current + timedelta(seconds=retry_after if failure else 900)).isoformat(),
    }
    audit(s, "source.sync", key, **row.state)
    return row.state
