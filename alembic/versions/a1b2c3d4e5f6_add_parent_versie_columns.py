"""add_parent_versie_columns

Revision ID: a1b2c3d4e5f6
Revises: 7dbce67b87f1
Create Date: 2026-04-12 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "7dbce67b87f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_chunk", sa.Column("parent_id", sa.String(), nullable=True, server_default="")
    )
    op.add_column(
        "knowledge_chunk", sa.Column("parent_content", sa.Text(), nullable=True, server_default="")
    )
    op.add_column(
        "knowledge_chunk", sa.Column("chapter_num", sa.Integer(), nullable=True, server_default="0")
    )
    op.add_column(
        "knowledge_chunk", sa.Column("chapter_title", sa.String(), nullable=True, server_default="")
    )
    op.add_column(
        "knowledge_chunk", sa.Column("versie", sa.String(), nullable=True, server_default="")
    )

    op.create_index(
        "idx_kc_parent",
        "knowledge_chunk",
        ["parent_id"],
        postgresql_where=sa.text("parent_id != ''"),
    )
    op.create_index(
        "idx_kc_versie", "knowledge_chunk", ["versie"], postgresql_where=sa.text("versie != ''")
    )


def downgrade() -> None:
    op.drop_index("idx_kc_versie", table_name="knowledge_chunk")
    op.drop_index("idx_kc_parent", table_name="knowledge_chunk")
    op.drop_column("knowledge_chunk", "versie")
    op.drop_column("knowledge_chunk", "chapter_title")
    op.drop_column("knowledge_chunk", "chapter_num")
    op.drop_column("knowledge_chunk", "parent_content")
    op.drop_column("knowledge_chunk", "parent_id")
