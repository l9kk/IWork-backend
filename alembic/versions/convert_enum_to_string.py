"""Convert enum columns to string

Revision ID: convert_enum_to_string
Revises: 3cd9b85186de
Create Date: 2025-03-30 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'convert_enum_to_string'
down_revision: Union[str, None] = '3cd9b85186de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('salaries', sa.Column('experience_level_new', sa.String(), nullable=True))
    op.add_column('salaries', sa.Column('employment_type_new', sa.String(), nullable=True))
    
    op.execute("UPDATE salaries SET experience_level_new = experience_level::text")
    op.execute("UPDATE salaries SET employment_type_new = employment_type::text")
    
    op.drop_column('salaries', 'experience_level')
    op.drop_column('salaries', 'employment_type')
    
    op.alter_column('salaries', 'experience_level_new', new_column_name='experience_level')
    op.alter_column('salaries', 'employment_type_new', new_column_name='employment_type')
    
    op.alter_column('salaries', 'experience_level', nullable=False)
    op.alter_column('salaries', 'employment_type', nullable=False, 
                    server_default="full-time")
    
    op.execute("DROP TYPE IF EXISTS experiencelevel")
    op.execute("DROP TYPE IF EXISTS employmenttype")


def downgrade() -> None:
    op.execute("CREATE TYPE experiencelevel AS ENUM ('intern', 'junior', 'middle', 'senior', 'executive')")
    op.execute("CREATE TYPE employmenttype AS ENUM ('full-time', 'part-time', 'contract', 'internship', 'freelance')")
    
    op.add_column('salaries', sa.Column('experience_level_enum', 
                                      postgresql.ENUM('intern', 'junior', 'middle', 'senior', 'executive', 
                                                   name='experiencelevel'), 
                                      nullable=True))
    op.add_column('salaries', sa.Column('employment_type_enum', 
                                      postgresql.ENUM('full-time', 'part-time', 'contract', 'internship', 'freelance', 
                                                   name='employmenttype'), 
                                      nullable=True))
    
    op.execute("UPDATE salaries SET experience_level_enum = experience_level::experiencelevel")
    op.execute("UPDATE salaries SET employment_type_enum = employment_type::employmenttype")
    
    op.drop_column('salaries', 'experience_level')
    op.drop_column('salaries', 'employment_type')
    
    op.alter_column('salaries', 'experience_level_enum', new_column_name='experience_level')
    op.alter_column('salaries', 'employment_type_enum', new_column_name='employment_type')
    
    op.alter_column('salaries', 'experience_level', nullable=False)
    op.alter_column('salaries', 'employment_type', nullable=False)
