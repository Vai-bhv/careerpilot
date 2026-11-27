#!/usr/bin/env bash
# Exercise a separate Compose project, database volume and private mount.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p private
work=$(mktemp -d "$PWD/private/compose-smoke.XXXXXXXX")
export CAREERPILOT_VOLUME="$work/private" CAREERPILOT_ENV_FILE="$work/compose.env"
mkdir -m 700 "$CAREERPILOT_VOLUME"
umask 077
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
printf 'POSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 24)" > "$CAREERPILOT_ENV_FILE"
project="careerpilot-test-$(openssl rand -hex 6)"
# Docker chooses ephemeral host ports for this test only.
export CAREERPILOT_PORT=0 CAREERPILOT_DASHBOARD_PORT=0
compose=(docker compose --env-file "$CAREERPILOT_ENV_FILE" -p "$project")
trap '"${compose[@]}" down --volumes >/dev/null; rm -rf -- "$work"' EXIT
"${compose[@]}" up --build --wait --wait-timeout 120 dashboard
addr=$("${compose[@]}" port api 8000)
ui=$("${compose[@]}" port dashboard 8501)
curl --retry 6 --retry-all-errors -fsS "http://$addr/health/ready"
curl --retry 6 --retry-all-errors -fsS "http://$ui/_stcore/health"
"${compose[@]}" exec -T api python - <<'PY'
from app.db import transaction
from app.demo import seed_session
from app.models import Job
from app.services.documents import generate, validate
from app.schemas import Generate
from sqlalchemy import select
with transaction() as s:
    seed_session(s)
    d=generate(s,s.scalar(select(Job).order_by(Job.id)),Generate())
    assert not validate(s,d) and d.snapshot["pages"]==1
    print("Compose PostgreSQL + PDF validated")
PY
