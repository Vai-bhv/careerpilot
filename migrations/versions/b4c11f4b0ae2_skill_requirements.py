"""Searchable skill requirements and typed professional and scheduling views."""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "b4c11f4b0ae2"
down_revision = "adba1fa8c5dd"
branch_labels = None
depends_on = None


def upgrade():
    skills = op.create_table(
        "skills",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False, unique=True),
    )
    requirements = op.create_table(
        "vacancy_skills",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("job_id", sa.Integer, sa.ForeignKey("vacancies.id"), nullable=False),
        sa.Column("skill_id", sa.Integer, sa.ForeignKey("skills.id"), nullable=False),
        sa.Column("requirement", sa.String(), nullable=False),
        sa.UniqueConstraint("job_id", "skill_id", "requirement"),
    )
    for field in ("job_id", "skill_id"):
        op.create_index("ix_vacancy_skills_" + field, "vacancy_skills", [field])
    vacancies = sa.table("vacancies", sa.column("id", sa.Integer), sa.column("fields", sa.JSON))
    conn = op.get_bind()
    known = {}
    for job_id, fields in conn.execute(sa.select(vacancies.c.id, vacancies.c.fields)):
        for kind in ("required", "preferred"):
            for skill in dict.fromkeys(fields.get(kind) or []):
                if skill not in known:
                    known[skill] = conn.execute(
                        skills.insert().values(name=skill, created=datetime.now(UTC))
                    ).inserted_primary_key[0]
                conn.execute(
                    requirements.insert().values(
                        job_id=job_id,
                        skill_id=known[skill],
                        requirement=kind,
                        created=datetime.now(UTC),
                    )
                )
    for view, kind in [
        ("employment_history", "employment"),
        ("projects", "project"),
        ("education", "education"),
        ("achievements", "achievement"),
    ]:
        op.execute(f"CREATE VIEW {view} AS SELECT * FROM evidence WHERE kind = '{kind}'")
    op.execute(
        "CREATE VIEW scheduled_jobs AS SELECT * FROM integrations WHERE name LIKE 'schedule/%'"
    )


def downgrade():
    for view in ("scheduled_jobs", "achievements", "education", "projects", "employment_history"):
        op.execute(f"DROP VIEW {view}")
    op.drop_table("vacancy_skills")
    op.drop_table("skills")
