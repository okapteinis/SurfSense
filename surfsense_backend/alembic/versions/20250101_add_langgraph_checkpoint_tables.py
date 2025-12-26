"""Add LangGraph checkpoint tables for message persistence.

Revision ID: 20250101_langgraph
Revises: 20240115_add_checkpoints
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250101_langgraph'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create checkpoint tables for LangGraph message persistence."""
    # Create checkpoint_blobs table
    op.create_table(
        'checkpoint_blobs',
        sa.Column('thread_id', sa.String(), nullable=False),
        sa.Column('checkpoint_id', sa.String(), nullable=False),
        sa.Column('blob_id', sa.String(), nullable=False),
        sa.Column('data', postgresql.BYTEA(), nullable=False),
        sa.PrimaryKeyConstraint('thread_id', 'checkpoint_id', 'blob_id'),
        schema=None
    )

    # Create checkpoint_writes table
    op.create_table(
        'checkpoint_writes',
        sa.Column('thread_id', sa.String(), nullable=False),
        sa.Column('checkpoint_id', sa.String(), nullable=False),
        sa.Column('channel', sa.String(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('data', postgresql.BYTEA(), nullable=False),
        sa.PrimaryKeyConstraint('thread_id', 'checkpoint_id', 'channel'),
        schema=None
    )

    # Create checkpoints table
    op.create_table(
        'checkpoints',
        sa.Column('thread_id', sa.String(), nullable=False),
        sa.Column('checkpoint_id', sa.String(), nullable=False),
        sa.Column('ts_ms', sa.BigInteger(), nullable=False),
        sa.Column('pending_sends', postgresql.BYTEA(), nullable=False),
        sa.Column('imminent', postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint('thread_id', 'checkpoint_id'),
        schema=None
    )

    # Create indexes for better query performance
    op.create_index('ix_checkpoints_thread_ts', 'checkpoints', ['thread_id', 'ts_ms'], unique=False)


def downgrade():
    """Remove checkpoint tables."""
    op.drop_index('ix_checkpoints_thread_ts', table_name='checkpoints')
    op.drop_table('checkpoints')
    op.drop_table('checkpoint_writes')
    op.drop_table('checkpoint_blobs')
