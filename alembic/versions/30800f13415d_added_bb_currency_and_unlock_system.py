"""added_bb_currency_and_unlock_system

Revision ID: 30800f13415d
Revises: 93fbe552157e
Create Date: 2026-05-01 23:01:46.140515

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '30800f13415d'
down_revision: Union[str, Sequence[str], None] = '93fbe552157e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add columns to users table
    op.add_column('users', sa.Column('bb_balance', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('last_login_reward_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('last_chat_reward_at', sa.DateTime(), nullable=True))
    
    # Set default balance for existing users
    op.execute("UPDATE users SET bb_balance = 100")

    # Create unlocked_players table
    op.create_table('unlocked_players',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('unlocked_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['player_id'], ['players.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_unlocked_players_id'), 'unlocked_players', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_unlocked_players_id'), table_name='unlocked_players')
    op.drop_table('unlocked_players')
    op.drop_column('users', 'last_chat_reward_at')
    op.drop_column('users', 'last_login_reward_at')
    op.drop_column('users', 'bb_balance')
