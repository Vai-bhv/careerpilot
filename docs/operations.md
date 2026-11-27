# Local operations

## Configuration

Run commands from the repository root. Environment variables take precedence over the ignored `.env` file. Set private file permissions with `chmod 600 .env`. An absent or blank `DATABASE_URL` selects `private/careerpilot.sqlite3`. A PostgreSQL URL uses the `postgresql+psycopg` driver. `careerpilot init` applies pending migrations and initializes a single candidate and bearer token. Repeating it preserves data. Compose applies migrations in a one-shot init container.

| Setting | Use |
| --- | --- |
| CAREERPILOT_PRIVATE | Directory for the native database fallback, token and worker lock |
| CAREERPILOT_TOKEN | Optional bearer token override. Otherwise read the owner-only token file |
| CAREERPILOT_API_URL | API used by Streamlit and stdio MCP |
| CAREERPILOT_LLM, OPENAI_MODEL, OLLAMA_MODEL | Initial provider and model, overridden by saved dashboard settings |
| CAREERPILOT_DAILY_USD | Hard daily ceiling for OpenAI. Zero disables paid requests |
| OPENAI_INPUT_USD_PER_MILLION, OPENAI_OUTPUT_USD_PER_MILLION | Current local model-specific price assumptions, both required for paid requests |
| OPENAI_API_KEY | Optional local secret for the chosen API account |
| CAREERPILOT_TIMEZONE | Scheduler timezone, initially Europe/Prague |
| CAREERPILOT_RETENTION_DAYS | Age threshold for the opt-in mail excerpt retention command |
| YAHOO_EMAIL, YAHOO_APP_PASSWORD, YAHOO_FOLDER, YAHOO_FROM, YAHOO_SEARCH | Read-only mailbox connection and search settings |
| CAREERPILOT_MAIL | Set to mock to use the fictional email adapter |

An external provider is optional. For local Ollama, install and start Ollama, obtain a suitable small model and set its installed tag. The native client connects to loopback port 11434. Host Ollama access from inside Compose needs a separately configured network arrangement. OpenAI requires API billing and a compatible chat-completions model that supports JSON output. Set the exact model’s current prices locally and keep the dashboard ceiling at or below the environment cap. Changing the model requires checking its prices. Cache hits reuse validated results. Before an external paid request a transaction reserves 4,096 input and 220 output tokens at configured rates. A successful response settles that reservation from reported usage. A timeout keeps the conservative reservation. Connection establishment can retry once. Provider errors fall back to deterministic ordering. Cost estimates depend on the configured prices.

## Export, retention and deletion

- **Single document**. Use the version-specific downloads in CV workspace. JSON includes evidence IDs. DOCX and PDF contain the application-facing text and hyperlinks.
- **SQLite workspace**. Stop the native launcher and worker. Copy the complete private directory, including original source files and the database, to an owner-only encrypted backup destination. The database contains original imported bytes, generated files and audit history. Protect the separate `.env` and token as secrets. Restore into a separate private directory and point `CAREERPILOT_PRIVATE` at it.
- **PostgreSQL workspace**. Run the following backup commands from the repository. Store the private template directory alongside the dump. Verify a restore into a fresh database before deleting the original. A template import alone does not transfer evidence review or submission history across databases.

```bash
mkdir -p private/backups
(umask 077; set -C; docker compose exec -T db pg_dump -U careerpilot -Fc careerpilot > "private/backups/careerpilot-$(date +%Y%m%d-%H%M%S).dump")
```

- **Age out mail excerpts**. Run `careerpilot retention --days 90` to preview. On explicit user choice, repeat with `--confirm`. This clears the subject, summary and links of old unlinked messages. Hashed identifiers remain for idempotency. Linked messages and application records remain in the workspace.
- **Reset without losing work**. Choose a new, empty `CAREERPILOT_PRIVATE` and a new database URL, or a separate Compose project name and private volume mount. Initialize the new workspace. Preserve the previous workspace until it can be deliberately retired.
- **Erase a workspace**. Stop its processes. Verify the exact workspace location, database identity and backup policy. Delete the selected SQLite database, originals, exports, backups and credential files through the local file manager. For a Compose workspace, `docker compose down --volumes` permanently deletes that project’s PostgreSQL volume. The bind-mounted private directory still requires separate deletion. Revoke the Yahoo app password and API key if the integration is retired. Full-disk encryption and backup retention govern recovery from underlying storage.

## Operational boundaries

The Streamlit app acts on behalf of the local OS user. Keep the loopback binding and use a trusted desktop account. Off-host or multi-user deployment requires a separate authentication, TLS and authorization design. PostgreSQL is persistent and uses health checks. Native SQLite and the scheduler target light single-user workloads. Source reads and PDF generation use synchronous timeouts. The dashboard reports integration execution history, including source errors and retry attempts.

The native launcher starts the API and dashboard together. Ctrl+C stops them. `docker compose down` stops Compose while keeping data. `scripts/test-postgres.sh` and `scripts/smoke-compose.sh` allocate unique disposable test environments. Use `scripts/scan.sh` after building `careerpilot-local:dev`.
