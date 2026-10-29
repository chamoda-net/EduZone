"""Baseline: the v1 schema.

Revision ID: 0001
Revises:
Create Date: 2026-10-29

Runs migrations/sql/0001_baseline.sql, a frozen copy of db/eduzone_v1_schema.sql
taken at this revision. Later schema changes go in new migrations (and are mirrored
in db/eduzone_v1_schema.sql); this file and its SQL never change.
"""

from pathlib import Path

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None

SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "0001_baseline.sql"


def upgrade() -> None:
    # Hand the whole script to psycopg directly: with no parameters it runs
    # multi-statement SQL as-is, so DO blocks and format('%I') are left alone.
    dbapi_conn = op.get_bind().connection.dbapi_connection
    assert dbapi_conn is not None
    with dbapi_conn.cursor() as cur:
        cur.execute(SQL_FILE.read_text(encoding="utf-8"))


def downgrade() -> None:
    raise NotImplementedError("The baseline cannot be downgraded; drop and recreate the database instead.")
