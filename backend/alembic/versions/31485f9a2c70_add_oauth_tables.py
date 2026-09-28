"""add_oauth_tables

Revision ID: 31485f9a2c70
Revises: 
Create Date: 2026-08-08 21:43:38.222611

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31485f9a2c70'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('accounts', 'password_hash', existing_type=sa.String(length=255), nullable=True)
    
    op.create_table(
        'oauth_accounts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('account_id', sa.UUID(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('provider_user_id', sa.String(length=255), nullable=False),
        sa.Column('provider_email', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'provider_user_id', name='uq_oauth_provider_user')
    )
    op.create_index('ix_oauth_accounts_account_id', 'oauth_accounts', ['account_id'])

    op.create_table(
        'oauth_states',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('state_token', sa.String(length=255), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('transaction_cookie_hash', sa.String(length=255), nullable=False),
        sa.Column('is_used', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('state_token', name='uq_oauth_states_state_token')
    )
    op.create_index('ix_oauth_states_state_token', 'oauth_states', ['state_token'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_oauth_states_state_token', table_name='oauth_states')
    op.drop_table('oauth_states')
    op.drop_index('ix_oauth_accounts_account_id', table_name='oauth_accounts')
    op.drop_table('oauth_accounts')
    op.alter_column('accounts', 'password_hash', existing_type=sa.String(length=255), nullable=False)
