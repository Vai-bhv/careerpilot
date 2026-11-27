#!/usr/bin/env bash
# Creates a new, loopback-only ephemeral container and stops only that container.
set -euo pipefail
cd "$(dirname "$0")/.."
export POSTGRES_PASSWORD
POSTGRES_PASSWORD=$(openssl rand -hex 20)
container=$(docker run --rm -d -p 127.0.0.1::5432 -e POSTGRES_PASSWORD postgres:16-alpine)
trap 'docker stop "$container" >/dev/null' EXIT
for _ in {1..45}; do
  if docker exec "$container" pg_isready -h 127.0.0.1 -U postgres >/dev/null; then break; fi
  sleep 1
done
port=$(docker port "$container" 5432/tcp)
export CAREERPILOT_TEST_POSTGRES="postgresql+psycopg://postgres:$POSTGRES_PASSWORD@127.0.0.1:${port##*:}/postgres"
.venv/bin/pytest -q "$@"
