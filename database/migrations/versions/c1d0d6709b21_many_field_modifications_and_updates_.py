"""many field modifications and updates including initial and final pH

Revision ID: c1d0d6709b21
Revises: 74802464b122
Create Date: 2025-03-21 13:59:34.102427

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d0d6709b21'
down_revision: Union[str, None] = '74802464b122'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('experimental_conditions', sa.Column('water_volume', sa.Float(), nullable=True))
    op.add_column('experimental_conditions', sa.Column('rock_mass', sa.Float(), nullable=True))
    op.add_column('experimental_conditions', sa.Column('catalyst_mass', sa.Float(), nullable=True))
    op.add_column('experimental_conditions', sa.Column('initial_ph', sa.Float(), nullable=True))
    op.add_column('experimental_conditions', sa.Column('final_ph', sa.Float(), nullable=True))
    op.add_column('experimental_conditions', sa.Column('buffer_concentration', sa.Float(), nullable=True))
    op.add_column('experimental_conditions', sa.Column('experiment_type', sa.String(), nullable=True))
    op.add_column('experimental_conditions', sa.Column('initial_nitrate_concentration', sa.Float(), nullable=True))
    op.add_column('experimental_conditions', sa.Column('dissolved_oxygen', sa.Float(), nullable=True))
    op.add_column('experimental_conditions', sa.Column('surfactant_type', sa.String(), nullable=True))
    op.add_column('experimental_conditions', sa.Column('surfactant_concentration', sa.Float(), nullable=True))
    op.add_column('experimental_conditions', sa.Column('co2_partial_pressure', sa.Float(), nullable=True))
    op.add_column('experimental_conditions', sa.Column('confining_pressure', sa.Float(), nullable=True))
    op.add_column('experimental_conditions', sa.Column('pore_pressure', sa.Float(), nullable=True))
    op.drop_column('experimental_conditions', 'ph')
    op.add_column('results', sa.Column('final_ph', sa.Float(), nullable=True))
    op.add_column('results', sa.Column('final_nitrate_concentration', sa.Float(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('results', 'final_nitrate_concentration')
    op.drop_column('results', 'final_ph')
    op.add_column('experimental_conditions', sa.Column('ph', sa.FLOAT(), nullable=True))
    op.drop_column('experimental_conditions', 'pore_pressure')
    op.drop_column('experimental_conditions', 'confining_pressure')
    op.drop_column('experimental_conditions', 'co2_partial_pressure')
    op.drop_column('experimental_conditions', 'surfactant_concentration')
    op.drop_column('experimental_conditions', 'surfactant_type')
    op.drop_column('experimental_conditions', 'dissolved_oxygen')
    op.drop_column('experimental_conditions', 'initial_nitrate_concentration')
    op.drop_column('experimental_conditions', 'experiment_type')
    op.drop_column('experimental_conditions', 'buffer_concentration')
    op.drop_column('experimental_conditions', 'final_ph')
    op.drop_column('experimental_conditions', 'initial_ph')
    op.drop_column('experimental_conditions', 'catalyst_mass')
    op.drop_column('experimental_conditions', 'rock_mass')
    op.drop_column('experimental_conditions', 'water_volume')
    # ### end Alembic commands ###
