import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(".env", override=False)


def private_root() -> Path:
    root = Path(os.getenv("CAREERPILOT_PRIVATE", "private")).resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def database_url() -> str:
    return os.getenv("DATABASE_URL") or f"sqlite:///{private_root()}/careerpilot.sqlite3"


def token() -> str:
    if configured := os.getenv("CAREERPILOT_TOKEN"):
        return configured
    path = private_root() / "api.token"
    return path.read_text().strip() if path.is_file() else ""


def init_secret() -> None:
    if token():
        return
    path = private_root() / "api.token"
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
        f.write(secrets.token_urlsafe(40))
