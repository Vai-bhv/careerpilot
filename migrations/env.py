from alembic import context

from app import models  # noqa: F401
from app.config import database_url
from app.db import Base, engine_for

with engine_for(database_url()).connect() as conn:
    context.configure(connection=conn, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
