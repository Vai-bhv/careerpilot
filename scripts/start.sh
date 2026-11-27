#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
umask 077
if [[ ${1:-personal} == demo ]]; then
  careerpilot demo
  export CAREERPILOT_PRIVATE="$PWD/private/demo-workspace"
  export DATABASE_URL="sqlite:///$CAREERPILOT_PRIVATE/demo.sqlite3"
  export CAREERPILOT_LLM=mock CAREERPILOT_MAIL=mock CAREERPILOT_DEMO=1
  export OPENAI_API_KEY="" CAREERPILOT_DAILY_USD=0
  export YAHOO_EMAIL="" YAHOO_APP_PASSWORD=""
else
  careerpilot init
fi
export CAREERPILOT_API_URL="http://127.0.0.1:${CAREERPILOT_PORT:-8000}"
python - "${CAREERPILOT_PORT:-8000}" "${CAREERPILOT_DASHBOARD_PORT:-8501}" <<'PYPORT'
import socket,sys
if sys.argv[1]==sys.argv[2]: raise SystemExit("Choose separate dashboard and API ports.")
for port in sys.argv[1:]:
    with socket.socket() as probe:
        try: probe.bind(("127.0.0.1",int(port)))
        except OSError as exc: raise SystemExit(f"Cannot bind localhost port {port}: {exc.strerror}")
PYPORT
uvicorn app.api.main:app --host 127.0.0.1 --port "${CAREERPILOT_PORT:-8000}" --no-access-log &
api_pid=$!
trap 'kill "$api_pid" 2>/dev/null || true' EXIT
for _ in {1..40}; do
  if curl -fsS "$CAREERPILOT_API_URL/health/ready" >/dev/null 2>&1; then break; fi
  kill -0 "$api_pid" || exit 1
  sleep 0.25
done
curl -fsS "$CAREERPILOT_API_URL/health/ready" >/dev/null || exit 1
kill -0 "$api_pid" || exit 1
streamlit run frontend/dashboard.py --server.address 127.0.0.1 --server.port "${CAREERPILOT_DASHBOARD_PORT:-8501}"
