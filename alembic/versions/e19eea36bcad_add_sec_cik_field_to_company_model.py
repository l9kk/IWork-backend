"""Add SEC CIK field to Company model

Revision ID: e19eea36bcad
Revises: 14f5ff45a6e4
Create Date: 2025-03-25 22:39:28.721261

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e19eea36bcad'
down_revision: Union[str, None] = '14f5ff45a6e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('companies', sa.Column('sec_cik', sa.String(), nullable=True))
    op.create_index(op.f('ix_companies_sec_cik'), 'companies', ['sec_cik'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_companies_sec_cik'), table_name='companies')
    op.drop_column('companies', 'sec_cik')
    # ### end Alembic commands ###
