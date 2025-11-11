"""initial migration

Revision ID: 0001_initial
Revises: 
Create Date: 2025-11-05 00:00:00.000000
"""
from alembic import op  # type: ignore
import sqlalchemy as sa  # type: ignore

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('product',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('price', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('image', sa.String(length=256), nullable=True),
        sa.Column('stock', sa.Integer(), nullable=True),
    )
    op.create_table('user',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('password_hash', sa.String(length=256), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=True),
    )


def downgrade():
    op.drop_table('user')
    op.drop_table('product')
