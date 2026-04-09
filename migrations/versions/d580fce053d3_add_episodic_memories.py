"""add_episodic_memories

Revision ID: d580fce053d3
Revises: c9fe3369e049
Create Date: 2026-04-06 09:12:34.651336

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = "d580fce053d3"
down_revision: Union[str, Sequence[str], None] = "c9fe3369e049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "episodic_memories",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(768), nullable=True),
        sa.Column("thread_id", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "CREATE INDEX ix_episodic_memories_embedding ON episodic_memories "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
    op.add_column(
        "conversations",
        sa.Column("consolidated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "consolidation_retries", sa.Integer(), server_default="0", nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("conversations", "consolidation_retries")
    op.drop_column("conversations", "consolidated_at")
    op.execute("DROP INDEX IF EXISTS ix_episodic_memories_embedding")
    op.drop_table("episodic_memories")
