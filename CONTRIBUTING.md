# Contributing

Use Python 3.12 and the pinned requirements in the README. Develop with a fictional workspace. Keep private evidence, real mail and candidate documents out of issues, screenshots, fixtures and pull requests.

Changes to schemas require an Alembic revision that can upgrade an existing workspace. Review all generated migration operations. Use a new empty database when testing migrations or submission flows. Preserve exact-version references and historical application records.

Run Ruff, pytest, the public-file check and any relevant PDF, PostgreSQL or MCP checks before requesting review. New source adapters need an official interface reference, terms and capability notes, bounded reads, idempotency and mocked failure tests. Record what was verified in PROGRESS.md.
