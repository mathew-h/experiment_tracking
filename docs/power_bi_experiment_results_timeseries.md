# Power BI: Experiment Results Time-Series

## Data Model

Star schema. Use integer keys for joins; string IDs for display only.

### Join Paths

```
sample_info.sample_id  --(1:M)-->  experiments.sample_id
experiments.id         --(1:M)-->  experimental_results.experiment_fk
experimental_results.id --(1:1)--> scalar_results.result_id
experimental_results.id --(1:1)--> icp_results.result_id
```

Chemical additives (indirect):
```
experiments.id -> experimental_conditions.experiment_fk
experimental_conditions.id -> chemical_additives.experiment_id
chemical_additives.compound_id -> compounds.id
```

Lineage (self-ref): `experiments.parent_experiment_fk -> experiments.id`

## Critical Filter

Always apply: `is_primary_timepoint_result = 1` (pre-applied in `v_primary_experiment_results`).

## View: v_primary_experiment_results

One row per primary timepoint per experiment. Scalar + ICP on same row when same timepoint.

### Time Axes

| Column | Use |
|--------|-----|
| `time_post_reaction_days` | Primary X-axis (days since reaction) |
| `time_post_reaction_bucket_days` | Aligned cross-experiment comparison |
| `cumulative_time_post_reaction_days` | Continuous axis across lineage chains |

### Identity

`experiment_id` (display), `experiment_fk` (joins), `result_id`, `result_description` (user-provided, not ICP label), `result_created_at`

### Scalar Results

`scalar_result_id`, `gross_ammonium_concentration_mM`, `background_ammonium_concentration_mM`, `grams_per_ton_yield`, `final_ph`, `final_nitrate_concentration_mM`, `ferrous_iron_yield`, `final_dissolved_oxygen_mg_L`, `final_conductivity_mS_cm`, `final_alkalinity_mg_L`, `co2_partial_pressure_MPa`, `sampling_volume_mL`, `ammonium_quant_method`, `background_experiment_fk`, `scalar_measurement_date`

### Hydrogen

`h2_concentration` (ppm), `h2_concentration_unit`, `gas_sampling_volume_ml`, `gas_sampling_pressure_MPa`, `h2_micromoles`, `h2_mass_ug`, `h2_grams_per_ton_yield`

### ICP Metadata

`icp_result_id`, `icp_dilution_factor`, `icp_raw_label`, `icp_analysis_date`, `icp_measurement_date`, `icp_sample_date`, `icp_instrument_used`

### ICP Elements (ppm)

`icp_fe_ppm` Fe, `icp_si_ppm` Si, `icp_ni_ppm` Ni, `icp_cu_ppm` Cu, `icp_mo_ppm` Mo, `icp_zn_ppm` Zn, `icp_mn_ppm` Mn, `icp_ca_ppm` Ca, `icp_cr_ppm` Cr, `icp_co_ppm` Co, `icp_mg_ppm` Mg, `icp_al_ppm` Al, `icp_sr_ppm` Sr, `icp_y_ppm` Y, `icp_nb_ppm` Nb, `icp_sb_ppm` Sb, `icp_cs_ppm` Cs, `icp_ba_ppm` Ba, `icp_nd_ppm` Nd, `icp_gd_ppm` Gd, `icp_pt_ppm` Pt, `icp_rh_ppm` Rh, `icp_ir_ppm` Ir, `icp_pd_ppm` Pd, `icp_ru_ppm` Ru, `icp_os_ppm` Os, `icp_tl_ppm` Tl

### Dimensions (not in view)

| Table | Key Columns |
|-------|-------------|
| `sample_info` | `sample_id` PK, `rock_classification`, `state`, `country`, `latitude`, `longitude` |
| `experiments` | `id` PK, `experiment_id`, `sample_id` FK, `parent_experiment_fk`, `status` |
| `experimental_conditions` | `experiment_fk` FK, `water_volume_mL`, `rock_mass_g`, `temperature_c`, `initial_ph` |
| `compounds` / `chemical_additives` | Additive details per experiment |

## Visualization Recipes

**H2 time-series:** X=`time_post_reaction_days`, Y=`h2_concentration`, Legend=`experiment_id`. Alt Y: `h2_grams_per_ton_yield`.

**Ammonium time-series:** X=`time_post_reaction_days`, Y=`gross_ammonium_concentration_mM`, Legend=`experiment_id`. Alt Y: `grams_per_ton_yield`.

**ICP dissolution:** X=`time_post_reaction_days`, Y=element columns, Legend=`experiment_id`. Unpivot `icp_*_ppm` columns in Power Query for multi-element legend.

**Combined dashboard:** Stack H2, ammonium, ICP panels sharing X-axis + `experiment_id` slicer.

**Lineage chain:** Use `cumulative_time_post_reaction_days` as X-axis. Child experiments continue the time axis.

**Geographic map:** `sample_info.latitude`/`longitude`. Join via `experiments.sample_id`.

## Key DAX

```dax
Net Ammonium (mM) = [gross_ammonium_concentration_mM] - [background_ammonium_concentration_mM]

// ICP element mass (ug) -- not stored, calculate in DAX
// Requires join to experimental_conditions for water_volume_mL
Fe Mass (ug) = SUM([icp_fe_ppm]) * SUM('experimental_conditions'[water_volume_mL])

Has Scalar Data = NOT ISBLANK([scalar_result_id])
Has ICP Data = NOT ISBLANK([icp_result_id])
```

## Power Query Tips

- Parse `icp_results.all_elements` JSON for rare elements beyond the 27 fixed columns.
- Unpivot `icp_*_ppm` columns for multi-element line charts with proper legend.
- Pivot `elemental_analysis` tall table for wide oxide matrix visuals.

## NULL Handling

Line charts skip NULLs (gaps). Use `NOT ISBLANK()` in aggregations. Conditional-format NULL cells in tables.

## Refresh

View recreated on app start. Public DB copy refreshed every 12h. Use Lab PC production DB for Power BI.
