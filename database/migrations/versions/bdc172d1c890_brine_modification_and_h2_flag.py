"""brine modification and h2 flag

Revision ID: bdc172d1c890
Revises: 4efd20d110e8
Create Date: 2026-03-17 00:00:00.000000

Adds brine_modification_description (TEXT NULL) and has_brine_modification
(BOOLEAN NOT NULL DEFAULT 0) to experimental_results.

Existing rows are safely backfilled: description = NULL, flag = 0 (FALSE).
An index on has_brine_modification is added for fast BI filtering.

SQLite notes:
- New nullable / defaulted columns can be added with simple ADD COLUMN (no batch needed).
- Views referencing experimental_results are dropped before the operation and
  recreated at the end of upgrade(). The event_listeners module also recreates
  them on every app startup, so this migration only needs to produce a
  consistent on-disk state immediately after running.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bdc172d1c890'
down_revision: Union[str, None] = '4efd20d110e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Shared view SQL helpers
# ---------------------------------------------------------------------------

_V_MODIFICATIONS = """
CREATE VIEW IF NOT EXISTS v_experimental_results_with_modifications AS
SELECT
    e.experiment_id                          AS experiment_id,
    er.id                                    AS result_id,
    er.experiment_fk                         AS experiment_fk,
    er.time_post_reaction_days               AS time_post_reaction_days,
    er.time_post_reaction_bucket_days        AS time_post_reaction_bucket_days,
    er.has_brine_modification                AS has_brine_modification,
    er.brine_modification_description        AS brine_modification_description,
    er.created_at                            AS result_created_at,
    er.updated_at                            AS result_updated_at
FROM experimental_results er
JOIN experiments e ON e.id = er.experiment_fk;
"""

# The full v_primary_experiment_results SQL is reproduced here so that after
# running this migration (without restarting the app) the view already
# contains the new columns.  event_listeners.py will also recreate it at
# next startup, which is the authoritative definition.
_V_PRIMARY = """
CREATE VIEW IF NOT EXISTS v_primary_experiment_results AS
WITH base AS (
    SELECT
        er.id,
        er.experiment_fk,
        er.time_post_reaction_days,
        COALESCE(er.time_post_reaction_bucket_days, ROUND(er.time_post_reaction_days, 4)) AS bucket_key,
        er.time_post_reaction_bucket_days,
        er.cumulative_time_post_reaction_days,
        er.description,
        er.brine_modification_description,
        er.has_brine_modification,
        er.created_at,
        er.is_primary_timepoint_result
    FROM experimental_results er
    WHERE er.is_primary_timepoint_result = 1
),
scalar_bucket AS (
    SELECT
        er.experiment_fk,
        COALESCE(er.time_post_reaction_bucket_days, ROUND(er.time_post_reaction_days, 4)) AS bucket_key,
        sr.*,
        ROW_NUMBER() OVER (
            PARTITION BY er.experiment_fk,
                         COALESCE(er.time_post_reaction_bucket_days, ROUND(er.time_post_reaction_days, 4))
            ORDER BY er.is_primary_timepoint_result DESC, er.id DESC
        ) AS rn
    FROM experimental_results er
    JOIN scalar_results sr ON sr.result_id = er.id
),
icp_bucket AS (
    SELECT
        er.experiment_fk,
        COALESCE(er.time_post_reaction_bucket_days, ROUND(er.time_post_reaction_days, 4)) AS bucket_key,
        icp.*,
        ROW_NUMBER() OVER (
            PARTITION BY er.experiment_fk,
                         COALESCE(er.time_post_reaction_bucket_days, ROUND(er.time_post_reaction_days, 4))
            ORDER BY er.is_primary_timepoint_result DESC, er.id DESC
        ) AS rn
    FROM experimental_results er
    JOIN icp_results icp ON icp.result_id = er.id
)
SELECT
    e.experiment_id                                  AS experiment_id,
    b.experiment_fk                                  AS experiment_fk,
    b.id                                             AS result_id,
    b.time_post_reaction_days                        AS time_post_reaction_days,
    b.time_post_reaction_bucket_days                 AS time_post_reaction_bucket_days,
    b.cumulative_time_post_reaction_days             AS cumulative_time_post_reaction_days,
    b.description                                    AS result_description,
    b.brine_modification_description                 AS brine_modification_description,
    b.has_brine_modification                         AS has_brine_modification,
    b.created_at                                     AS result_created_at,

    -- Scalar Results (resolved by experiment + time bucket)
    sr.id                                            AS scalar_result_id,
    sr.gross_ammonium_concentration_mM               AS gross_ammonium_concentration_mM,
    sr.background_ammonium_concentration_mM          AS background_ammonium_concentration_mM,
    sr.grams_per_ton_yield                           AS grams_per_ton_yield,
    sr.final_ph                                      AS final_ph,
    sr.final_nitrate_concentration_mM                AS final_nitrate_concentration_mM,
    sr.ferrous_iron_yield                            AS ferrous_iron_yield,
    sr.final_dissolved_oxygen_mg_L                   AS final_dissolved_oxygen_mg_L,
    sr.final_conductivity_mS_cm                      AS final_conductivity_mS_cm,
    sr.final_alkalinity_mg_L                         AS final_alkalinity_mg_L,
    sr.co2_partial_pressure_MPa                      AS co2_partial_pressure_MPa,
    sr.sampling_volume_mL                            AS sampling_volume_mL,
    sr.ammonium_quant_method                         AS ammonium_quant_method,
    sr.background_experiment_fk                      AS background_experiment_fk,
    sr.measurement_date                              AS scalar_measurement_date,

    -- Hydrogen Data
    sr.h2_concentration                              AS h2_concentration,
    sr.h2_concentration_unit                         AS h2_concentration_unit,
    sr.gas_sampling_volume_ml                        AS gas_sampling_volume_ml,
    sr.gas_sampling_pressure_MPa                     AS gas_sampling_pressure_MPa,
    sr.h2_micromoles                                 AS h2_micromoles,
    sr.h2_mass_ug                                    AS h2_mass_ug,
    sr.h2_grams_per_ton_yield                        AS h2_grams_per_ton_yield,
    CASE WHEN sr.h2_concentration IS NOT NULL THEN 1 ELSE 0 END AS has_h2_measurement,

    -- ICP Results (resolved by experiment + time bucket)
    icp.id                                           AS icp_result_id,
    icp.dilution_factor                              AS icp_dilution_factor,
    icp.raw_label                                    AS icp_raw_label,
    icp.measurement_date                             AS icp_measurement_date,
    icp.sample_date                                  AS icp_sample_date,
    icp.instrument_used                              AS icp_instrument_used,

    -- ICP Elements
    icp.fe  AS icp_fe_ppm,
    icp.si  AS icp_si_ppm,
    icp.ni  AS icp_ni_ppm,
    icp.cu  AS icp_cu_ppm,
    icp.mo  AS icp_mo_ppm,
    icp.zn  AS icp_zn_ppm,
    icp.mn  AS icp_mn_ppm,
    icp.ca  AS icp_ca_ppm,
    icp.cr  AS icp_cr_ppm,
    icp.co  AS icp_co_ppm,
    icp.mg  AS icp_mg_ppm,
    icp.al  AS icp_al_ppm,
    icp.sr  AS icp_sr_ppm,
    icp.y   AS icp_y_ppm,
    icp.nb  AS icp_nb_ppm,
    icp.sb  AS icp_sb_ppm,
    icp.cs  AS icp_cs_ppm,
    icp.ba  AS icp_ba_ppm,
    icp.nd  AS icp_nd_ppm,
    icp.gd  AS icp_gd_ppm,
    icp.pt  AS icp_pt_ppm,
    icp.rh  AS icp_rh_ppm,
    icp.ir  AS icp_ir_ppm,
    icp.pd  AS icp_pd_ppm,
    icp.ru  AS icp_ru_ppm,
    icp.os  AS icp_os_ppm,
    icp.tl  AS icp_tl_ppm

FROM base b
JOIN experiments e ON e.id = b.experiment_fk
LEFT JOIN scalar_bucket sr
    ON sr.experiment_fk = b.experiment_fk
   AND sr.bucket_key    = b.bucket_key
   AND sr.rn = 1
LEFT JOIN icp_bucket icp
    ON icp.experiment_fk = b.experiment_fk
   AND icp.bucket_key    = b.bucket_key
   AND icp.rn = 1;
"""


def upgrade() -> None:
    """Add brine modification columns to experimental_results — SQLite compatible, idempotent."""
    from alembic import context
    from sqlalchemy import inspect

    conn = context.get_context().bind
    inspector = inspect(conn)
    all_tables = inspector.get_table_names()

    # ------------------------------------------------------------------
    # 0a. Clean up any leftover temp table from a failed prior downgrade
    #     (batch_alter_table in downgrade() creates _alembic_tmp_experimental_results;
    #     if that run failed, re-running upgrade without cleanup would error)
    # ------------------------------------------------------------------
    if '_alembic_tmp_experimental_results' in all_tables:
        op.drop_table('_alembic_tmp_experimental_results')

    # ------------------------------------------------------------------
    # 0b. Drop views that reference experimental_results before schema ops
    # ------------------------------------------------------------------
    op.execute("DROP VIEW IF EXISTS v_primary_experiment_results")
    op.execute("DROP VIEW IF EXISTS v_experimental_results_with_modifications")

    # ------------------------------------------------------------------
    # 1. Add new columns (simple ADD COLUMN — no batch needed for SQLite
    #    when columns are nullable or have a server_default)
    # ------------------------------------------------------------------
    er_columns = [col['name'] for col in inspector.get_columns('experimental_results')]

    if 'brine_modification_description' not in er_columns:
        op.add_column(
            'experimental_results',
            sa.Column('brine_modification_description', sa.Text(), nullable=True),
        )

    if 'has_brine_modification' not in er_columns:
        op.add_column(
            'experimental_results',
            sa.Column(
                'has_brine_modification',
                sa.Boolean(),
                server_default=sa.text('0'),
                nullable=False,
            ),
        )

    # ------------------------------------------------------------------
    # 2. Explicit backfill (server_default handles new rows; this covers
    #    any edge-case where SQLite left existing rows with NULL)
    # ------------------------------------------------------------------
    op.execute(
        "UPDATE experimental_results "
        "SET has_brine_modification = 0 "
        "WHERE has_brine_modification IS NULL"
    )

    # ------------------------------------------------------------------
    # 3. Add index for fast BI / Power BI filtering on the boolean flag
    # ------------------------------------------------------------------
    er_indexes = [idx['name'] for idx in inspector.get_indexes('experimental_results')]

    if 'ix_experimental_results_has_brine_modification' not in er_indexes:
        op.create_index(
            'ix_experimental_results_has_brine_modification',
            'experimental_results',
            ['has_brine_modification'],
            unique=False,
        )

    # ------------------------------------------------------------------
    # 4. Recreate views with the new columns included
    # ------------------------------------------------------------------
    op.execute(_V_PRIMARY)
    op.execute(_V_MODIFICATIONS)


def downgrade() -> None:
    """Remove brine modification columns — SQLite compatible, idempotent."""
    from alembic import context
    from sqlalchemy import inspect

    conn = context.get_context().bind
    inspector = inspect(conn)
    all_tables = inspector.get_table_names()

    # ------------------------------------------------------------------
    # 0a. Clean up any leftover temp table from a failed prior downgrade
    #     batch_alter_table creates _alembic_tmp_experimental_results;
    #     if a previous run failed mid-rename, re-running downgrade would error
    # ------------------------------------------------------------------
    if '_alembic_tmp_experimental_results' in all_tables:
        op.drop_table('_alembic_tmp_experimental_results')

    # ------------------------------------------------------------------
    # 0b. Drop views before batch operations (SQLite validates view
    #     dependencies during the batch rename step and will error if
    #     any view still references experimental_results)
    # ------------------------------------------------------------------
    op.execute("DROP VIEW IF EXISTS v_primary_experiment_results")
    op.execute("DROP VIEW IF EXISTS v_experimental_results_with_modifications")

    # ------------------------------------------------------------------
    # 1. Drop index
    # ------------------------------------------------------------------
    er_indexes = [idx['name'] for idx in inspector.get_indexes('experimental_results')]

    if 'ix_experimental_results_has_brine_modification' in er_indexes:
        op.drop_index(
            'ix_experimental_results_has_brine_modification',
            table_name='experimental_results',
        )

    # ------------------------------------------------------------------
    # 2. Drop columns via batch_alter_table (required for SQLite)
    # ------------------------------------------------------------------
    er_columns = [col['name'] for col in inspector.get_columns('experimental_results')]
    cols_to_drop = [
        c for c in ('has_brine_modification', 'brine_modification_description')
        if c in er_columns
    ]

    if cols_to_drop:
        with op.batch_alter_table('experimental_results', schema=None) as batch_op:
            for col in cols_to_drop:
                batch_op.drop_column(col)

    # ------------------------------------------------------------------
    # 3. Recreate pre-migration version of v_primary_experiment_results
    #    (without brine / h2 columns). event_listeners will refresh on
    #    next startup.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE VIEW IF NOT EXISTS v_primary_experiment_results AS
        WITH base AS (
            SELECT
                er.id,
                er.experiment_fk,
                er.time_post_reaction_days,
                COALESCE(er.time_post_reaction_bucket_days,
                         ROUND(er.time_post_reaction_days, 4)) AS bucket_key,
                er.time_post_reaction_bucket_days,
                er.cumulative_time_post_reaction_days,
                er.description,
                er.created_at,
                er.is_primary_timepoint_result
            FROM experimental_results er
            WHERE er.is_primary_timepoint_result = 1
        ),
        scalar_bucket AS (
            SELECT
                er.experiment_fk,
                COALESCE(er.time_post_reaction_bucket_days,
                         ROUND(er.time_post_reaction_days, 4)) AS bucket_key,
                sr.*,
                ROW_NUMBER() OVER (
                    PARTITION BY er.experiment_fk,
                                 COALESCE(er.time_post_reaction_bucket_days,
                                          ROUND(er.time_post_reaction_days, 4))
                    ORDER BY er.is_primary_timepoint_result DESC, er.id DESC
                ) AS rn
            FROM experimental_results er
            JOIN scalar_results sr ON sr.result_id = er.id
        ),
        icp_bucket AS (
            SELECT
                er.experiment_fk,
                COALESCE(er.time_post_reaction_bucket_days,
                         ROUND(er.time_post_reaction_days, 4)) AS bucket_key,
                icp.*,
                ROW_NUMBER() OVER (
                    PARTITION BY er.experiment_fk,
                                 COALESCE(er.time_post_reaction_bucket_days,
                                          ROUND(er.time_post_reaction_days, 4))
                    ORDER BY er.is_primary_timepoint_result DESC, er.id DESC
                ) AS rn
            FROM experimental_results er
            JOIN icp_results icp ON icp.result_id = er.id
        )
        SELECT
            e.experiment_id AS experiment_id,
            b.experiment_fk AS experiment_fk,
            b.id AS result_id,
            b.time_post_reaction_days AS time_post_reaction_days,
            b.time_post_reaction_bucket_days AS time_post_reaction_bucket_days,
            b.cumulative_time_post_reaction_days AS cumulative_time_post_reaction_days,
            b.description AS result_description,
            b.created_at AS result_created_at,
            sr.id AS scalar_result_id,
            sr.gross_ammonium_concentration_mM AS gross_ammonium_concentration_mM,
            sr.background_ammonium_concentration_mM AS background_ammonium_concentration_mM,
            sr.grams_per_ton_yield AS grams_per_ton_yield,
            sr.final_ph AS final_ph,
            sr.final_nitrate_concentration_mM AS final_nitrate_concentration_mM,
            sr.ferrous_iron_yield AS ferrous_iron_yield,
            sr.final_dissolved_oxygen_mg_L AS final_dissolved_oxygen_mg_L,
            sr.final_conductivity_mS_cm AS final_conductivity_mS_cm,
            sr.final_alkalinity_mg_L AS final_alkalinity_mg_L,
            sr.co2_partial_pressure_MPa AS co2_partial_pressure_MPa,
            sr.sampling_volume_mL AS sampling_volume_mL,
            sr.ammonium_quant_method AS ammonium_quant_method,
            sr.background_experiment_fk AS background_experiment_fk,
            sr.measurement_date AS scalar_measurement_date,
            sr.h2_concentration AS h2_concentration,
            sr.h2_concentration_unit AS h2_concentration_unit,
            sr.gas_sampling_volume_ml AS gas_sampling_volume_ml,
            sr.gas_sampling_pressure_MPa AS gas_sampling_pressure_MPa,
            sr.h2_micromoles AS h2_micromoles,
            sr.h2_mass_ug AS h2_mass_ug,
            sr.h2_grams_per_ton_yield AS h2_grams_per_ton_yield,
            icp.id AS icp_result_id,
            icp.dilution_factor AS icp_dilution_factor,
            icp.raw_label AS icp_raw_label,
            icp.measurement_date AS icp_measurement_date,
            icp.sample_date AS icp_sample_date,
            icp.instrument_used AS icp_instrument_used,
            icp.fe AS icp_fe_ppm, icp.si AS icp_si_ppm,
            icp.ni AS icp_ni_ppm, icp.cu AS icp_cu_ppm,
            icp.mo AS icp_mo_ppm, icp.zn AS icp_zn_ppm,
            icp.mn AS icp_mn_ppm, icp.ca AS icp_ca_ppm,
            icp.cr AS icp_cr_ppm, icp.co AS icp_co_ppm,
            icp.mg AS icp_mg_ppm, icp.al AS icp_al_ppm,
            icp.sr AS icp_sr_ppm, icp.y  AS icp_y_ppm,
            icp.nb AS icp_nb_ppm, icp.sb AS icp_sb_ppm,
            icp.cs AS icp_cs_ppm, icp.ba AS icp_ba_ppm,
            icp.nd AS icp_nd_ppm, icp.gd AS icp_gd_ppm,
            icp.pt AS icp_pt_ppm, icp.rh AS icp_rh_ppm,
            icp.ir AS icp_ir_ppm, icp.pd AS icp_pd_ppm,
            icp.ru AS icp_ru_ppm, icp.os AS icp_os_ppm,
            icp.tl AS icp_tl_ppm
        FROM base b
        JOIN experiments e ON e.id = b.experiment_fk
        LEFT JOIN scalar_bucket sr
            ON sr.experiment_fk = b.experiment_fk
           AND sr.bucket_key    = b.bucket_key
           AND sr.rn = 1
        LEFT JOIN icp_bucket icp
            ON icp.experiment_fk = b.experiment_fk
           AND icp.bucket_key    = b.bucket_key
           AND icp.rn = 1;
        """
    )
