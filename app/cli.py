import argparse
import json
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from app.config import init_secret
from app.db import transaction
from app.models import Evidence, Profile
from app.schemas import Preferences
from app.services.jobs import import_rows
from app.services.templates import import_template, variant_for


def initialize():
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    init_secret()
    with transaction() as s:
        if s.get(Profile, 1) is None:
            s.add(Profile(id=1, preferences=Preferences().model_dump()))


def import_directory(directory):
    paths = list(directory.iterdir())
    with transaction() as s:
        imported = []
        for variant in sorted({v for p in paths if (v := variant_for(p))}):
            files = sorted(
                (
                    p
                    for p in paths
                    if variant_for(p) == variant and p.suffix.lower() in {".docx", ".pdf"}
                ),
                key=lambda p: (p.suffix.lower() != ".docx", p.name),
            )
            if files:
                from app.repo import Problem

                for index, p in enumerate(files):
                    try:
                        with s.begin_nested():
                            item = import_template(s, p.name, p.read_bytes(), variant)
                        imported.append(item.variant)
                        break
                    except Problem:
                        if index == len(files) - 1:
                            raise
        count = len(list(s.scalars(select(Evidence.id))))
        return {"variants": imported, "evidence_records": count}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description="CareerPilot local workspace")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("init")
    imp = commands.add_parser("import-templates")
    imp.add_argument("directory", type=Path)
    jobs = commands.add_parser("import-jobs")
    jobs.add_argument("file", type=Path)
    commands.add_parser("demo")
    commands.add_parser("worker")
    retention = commands.add_parser("retention", help="Preview expired unlinked mail excerpts")
    retention.add_argument(
        "--days", type=int, default=int(os.getenv("CAREERPILOT_RETENTION_DAYS", "90"))
    )
    retention.add_argument(
        "--confirm", action="store_true", help="Permanently erase the listed expired excerpts"
    )
    args = parser.parse_args()
    if args.action == "init":
        initialize()
        print("Database migrated and local authentication initialized.")
    elif args.action == "import-templates":
        print(json.dumps(import_directory(args.directory)))
    elif args.action == "import-jobs":
        import csv

        with args.file.open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f)) if args.file.suffix.lower() == ".csv" else json.load(f)
        with transaction() as s:
            print(json.dumps(import_rows(s, rows if isinstance(rows, list) else [rows])))
    elif args.action == "demo":
        from app.demo import seed

        seed()
    elif args.action == "retention":
        from app.services.privacy import expire_mail

        if args.days < 1:
            parser.error("Retention must be at least one day")
        with transaction() as s:
            print(json.dumps(expire_mail(s, args.days, args.confirm)))
    elif args.action == "worker":
        from app.scheduler import run

        run()


if __name__ == "__main__":
    main()
