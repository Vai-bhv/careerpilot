# One local workspace per candidate

FastAPI, Streamlit, the CLI, the scheduler and the stdio MCP bridge share one Python distribution. The dashboard and MCP client use the authenticated API. Use one database per candidate. A separate database and private directory isolate the fictional demo.

PostgreSQL is the Compose deployment database. SQLite provides a native offline option on machines with only the PostgreSQL client. Both use the same SQLAlchemy models, transactions and Alembic revisions. Original templates and immutable generated files live in the same database as their evidence and approvals so rollback covers their contents. Local secret files live outside version control.

Professional facts are reviewable evidence rows. Employment headers, project identities and education records are typed evidence so the same disclosure and revision rules apply to every factual section. Template citations connect one fact to multiple source paragraphs. Provider-generated prose has no permission to create evidence or approve a document.
