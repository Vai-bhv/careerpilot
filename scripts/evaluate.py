"""Evaluate a fixed fictional candidate in a fresh throwaway database."""

import argparse
import os
import tempfile
from pathlib import Path

from sqlalchemy import select

from app.cli import initialize
from app.db import transaction
from app.demo import demo_jobs, seed_session
from app.models import Job
from app.schemas import Generate
from app.services.documents import generate, validate
from app.services.matching import match


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matching-only", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["CAREERPILOT_PRIVATE"] = tmp
        os.environ["DATABASE_URL"] = f"sqlite:///{Path(tmp) / 'evaluation.db'}"
        initialize()
        with transaction() as s:
            seed_session(s, evaluation=True)
            labels = {r["job"]["title"]: r for r in demo_jobs()}
            correct = tp = fp = fn = valid = links = claims = 0
            ranked = []
            preferred_tp = preferred_fp = preferred_fn = 0
            for job in s.scalars(select(Job).order_by(Job.id)):
                truth = labels[job.title]
                r = match(s, job)
                correct += r["fit"] == truth["label"]
                expected = set(truth["required"])
                extracted = set(job.fields["required"] or [])
                tp += len(expected & extracted)
                fp += len(extracted - expected)
                fn += len(expected - extracted)
                if "preferred" in truth:
                    expected_preferred = set(truth["preferred"])
                    extracted_preferred = set(job.fields["preferred"] or [])
                    preferred_tp += len(expected_preferred & extracted_preferred)
                    preferred_fp += len(extracted_preferred - expected_preferred)
                    preferred_fn += len(expected_preferred - extracted_preferred)
                if not args.matching_only:
                    doc = generate(s, job, Generate())
                    valid += not validate(s, doc) and doc.snapshot["pages"] == 1
                    claims += len(doc.snapshot["claims"])
                    links += sum(bool(c["link"]) for c in doc.snapshot["claims"])
                ranked.append((r["score"], job.title, r["fit"], truth["label"]))
            for score, title, band, label in sorted(ranked, reverse=True):
                print(f"{score:3}  {title} | predicted {band} | labelled {label}")
            print(f"Fit bands {correct}/{len(labels)}. Required-skill TP {tp}, FP {fp}, FN {fn}.")
            print(f"Preferred-skill TP {preferred_tp}, FP {preferred_fp}, FN {preferred_fn}.")
            if not args.matching_only:
                print(
                    f"Validated one-page exports {valid}/{len(labels)}, evidence references {claims}, hyperlink occurrences {links}."
                )


if __name__ == "__main__":
    main()
