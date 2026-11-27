"""Fail if private artifacts or likely credentials enter the public Git file set."""

import re
import subprocess
from pathlib import Path


def main():
    files = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
        )
        .decode()
        .split("\0")
    )
    errors = []
    for path in filter(None, files):
        p = Path(path)
        if not p.is_file():
            continue
        if (
            p.is_symlink()
            or p.parts[0] == "private"
            or p.name.startswith(".env")
            and p.name != ".env.example"
            or p.suffix.lower()
            in {".pdf", ".docx", ".db", ".sqlite", ".sqlite3", ".dump", ".pem", ".key"}
            or (p.suffix == ".eml" and p.parent != Path("tests/fixtures"))
        ):
            errors.append(path)
            continue
        if p.suffix.lower() in {".png", ".jpg"}:
            continue
        content = p.read_text(errors="replace")
        secret = re.search(
            r"(?:sk-(?:proj-)?[A-Za-z0-9_-]{30,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)",
            content,
        )
        if secret:
            errors.append(path)
    if errors:
        raise SystemExit("Review these public file paths: " + ", ".join(errors))
    print("Public-file privacy check passed.")


if __name__ == "__main__":
    main()
