"""add experimental data and enhance modifications log

Revision ID: add_experimental_data
Revises: 
Create Date: 2024-03-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_experimental_data'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create experimental_data table
    op.create_table(
        'experimental_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('experiment_id', sa.Integer(), nullable=True),
        sa.Column('data_type', sa.String(), nullable=True),
        sa.Column('file_path', sa.String(), nullable=True),
        sa.Column('file_name', sa.String(), nullable=True),
        sa.Column('file_type', sa.String(), nullable=True),
        sa.Column('data_values', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['experiment_id'], ['experiments.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_experimental_data_id'), 'experimental_data', ['id'], unique=False)

    # Add cascade delete to modifications_log
    op.drop_constraint('modifications_log_experiment_id_fkey', 'modifications_log', type_='foreignkey')
    op.create_foreign_key(
        'modifications_log_experiment_id_fkey',
        'modifications_log',
        'experiments',
        ['experiment_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Add cascade delete to experiment_notes
    op.drop_constraint('experiment_notes_experiment_id_fkey', 'experiment_notes', type_='foreignkey')
    op.create_foreign_key(
        'experiment_notes_experiment_id_fkey',
        'experiment_notes',
        'experiments',
        ['experiment_id'],
        ['id'],
        ondelete='CASCADE'
    )

def downgrade():
    # Remove cascade delete from experiment_notes
    op.drop_constraint('experiment_notes_experiment_id_fkey', 'experiment_notes', type_='foreignkey')
    op.create_foreign_key(
        'experiment_notes_experiment_id_fkey',
        'experiment_notes',
        'experiments',
        ['experiment_id'],
        ['id']
    )

    # Remove cascade delete from modifications_log
    op.drop_constraint('modifications_log_experiment_id_fkey', 'modifications_log', type_='foreignkey')
    op.create_foreign_key(
        'modifications_log_experiment_id_fkey',
        'modifications_log',
        'experiments',
        ['experiment_id'],
        ['id']
    )

    # Drop experimental_data table
    op.drop_index(op.f('ix_experimental_data_id'), table_name='experimental_data')
    op.drop_table('experimental_data') 