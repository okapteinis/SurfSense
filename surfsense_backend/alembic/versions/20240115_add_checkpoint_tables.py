"""Add checkpoint tables for message persistence.

Revision ID: 20240115_add_checkpoints
Revises:
Create Date: 2024-01-15 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20240115_add_checkpoints'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create checkpoint tables for message persistence."""
    # Create conversation_checkpoints table
    op.create_table(
        'conversation_checkpoints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.String(length=256), nullable=False, index=True),
        sa.Column('checkpoint_id', sa.String(length=256), nullable=False, unique=True, index=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create conversation_messages table
    op.create_table(
        'conversation_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.String(length=256), nullable=False, index=True),
        sa.Column('checkpoint_id', sa.String(length=256), nullable=False, index=True),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create agent_state_snapshots table
    op.create_table(
        'agent_state_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.String(length=256), nullable=False, unique=True, index=True),
        sa.Column('checkpoint_id', sa.String(length=256), nullable=False, index=True),
        sa.Column('state_data', sa.JSON(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create indexes for better query performance
    op.create_index(
        'idx_conversation_messages_checkpoint',
        'conversation_messages',
        ['conversation_id', 'checkpoint_id'],
        unique=False
    )
    op.create_index(
        'idx_checkpoints_timestamp',
        'conversation_checkpoints',
        ['conversation_id', 'timestamp'],
        unique=False
    )


def downgrade() -> None:
    """Drop checkpoint tables."""
    # Drop indexes
    op.drop_index('idx_checkpoints_timestamp', table_name='conversation_checkpoints')
    op.drop_index('idx_conversation_messages_checkpoint', table_name='conversation_messages')
    
    # Drop tables
    op.drop_table('agent_state_snapshots')
    op.drop_table('conversation_messages')
    op.drop_table('conversation_checkpoints')
