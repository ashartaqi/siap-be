"""add document_embeddings table

Revision ID: 6b68fe4f9734
Revises: 819d18022a66
Create Date: 2026-07-06 14:40:32.900779

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '6b68fe4f9734'
down_revision: Union[str, Sequence[str], None] = '819d18022a66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table('document_embeddings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('source_type', sa.String(), nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('content', sa.String(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_embeddings_id'), 'document_embeddings', ['id'], unique=False)
    op.create_index(op.f('ix_document_embeddings_source_id'), 'document_embeddings', ['source_id'], unique=False)
    op.create_index(op.f('ix_document_embeddings_source_type'), 'document_embeddings', ['source_type'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_document_embeddings_source_type'), table_name='document_embeddings')
    op.drop_index(op.f('ix_document_embeddings_source_id'), table_name='document_embeddings')
    op.drop_index(op.f('ix_document_embeddings_id'), table_name='document_embeddings')
    op.drop_table('document_embeddings')
    # ### end Alembic commands ###