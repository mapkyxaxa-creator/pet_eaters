"""Add ban fields to User

Revision ID: f706ce4773ef
Revises: aa146f2fa9bd
Create Date: 2026-08-20 14:03:54.046212

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f706ce4773ef'
down_revision: Union[str, None] = 'aa146f2fa9bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ✅ ИСПРАВЛЕНО: добавлен server_default для NOT NULL колонки
    op.add_column('users', sa.Column('is_banned', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('ban_reason', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('banned_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('referred_by', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'referred_by')
    op.drop_column('users', 'banned_at')
    op.drop_column('users', 'ban_reason')
    op.drop_column('users', 'is_banned')