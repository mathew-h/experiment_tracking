# Ferrous Iron Yield (%) — Implementation Plan

## Overview

Two new calculated fields will be added to `ScalarResults` to quantify how much of the initial ferrous iron (Fe²⁺) in the system is consumed, inferred from two independent product measurements: **H₂** and **NH₃**. Both calculations require a new input field, `total_ferrous_iron` (grams), on the `ExperimentalConditions` model.

---

## 1. Chemistry & Stoichiometry

### 1a. H₂-Derived Ferrous Iron Yield

During magnetite (Fe₃O₄) formation, ferrous iron is oxidized and H₂ is generated. The stoichiometric relationship is:

> **3 mol Fe²⁺ → 1 mol H₂**

Given a measured quantity of H₂ (already stored as `h2_micromoles`), back-calculate the Fe²⁺ consumed:

```
Fe²⁺_consumed_µmol = h2_micromoles × 3
Fe²⁺_consumed_g    = (Fe²⁺_consumed_µmol / 1,000,000) × 55.845   # molar mass of Fe
Yield (%)           = (Fe²⁺_consumed_g / total_ferrous_iron_g) × 100
```

**Worked example:** 1000 µmol H₂ → 3000 µmol Fe²⁺ = 0.003 mol × 55.845 g/mol = **0.168 g Fe²⁺** consumed.

### 1b. NH₃-Derived Ferrous Iron Yield

Ammonia generation from nitrate reduction coupled with iron oxidation follows:

> **9 mol Fe²⁺ → 2 mol NH₃**

Total ammonia moles are derived from the net ammonium concentration and solution volume:

```
net_ammonium_mM     = max(0, gross_ammonium_concentration_mM − background_ammonium_concentration_mM)
solution_volume_mL  = sampling_volume_mL (if available) OR water_volume_mL (from conditions)
total_NH3_mol       = (net_ammonium_mM / 1000) × (solution_volume_mL / 1000)

Fe²⁺_consumed_mol  = total_NH3_mol × (9 / 2)
Fe²⁺_consumed_g    = Fe²⁺_consumed_mol × 55.845
Yield (%)           = (Fe²⁺_consumed_g / total_ferrous_iron_g) × 100
```

---

## 2. Schema Changes

### 2a. `ExperimentalConditions` — new column

| Column              | Type    | Nullable | Unit   | Notes                           |
|---------------------|---------|----------|--------|---------------------------------|
| `total_ferrous_iron`| `Float` | `True`   | grams  | Initial Fe²⁺ mass in the system |

**File:** `database/models/conditions.py`

Add after the `initial_alkalinity` field:

```python
total_ferrous_iron = Column(Float, nullable=True)  # grams of initial Fe(II)
```

### 2b. `ScalarResults` — new columns

| Column                            | Type    | Nullable | Unit | Readonly | Notes                           |
|-----------------------------------|---------|----------|------|----------|---------------------------------|
| `ferrous_iron_yield_h2_pct`      | `Float` | `True`   | %    | Yes      | H₂-derived Fe²⁺ yield          |
| `ferrous_iron_yield_nh3_pct`     | `Float` | `True`   | %    | Yes      | NH₃-derived Fe²⁺ yield         |

**File:** `database/models/results.py`

Add alongside existing H₂ derived fields (after `h2_grams_per_ton_yield`):

```python
ferrous_iron_yield_h2_pct = Column(Float, nullable=True)   # H2-derived Fe(II) yield (%)
ferrous_iron_yield_nh3_pct = Column(Float, nullable=True)   # NH3-derived Fe(II) yield (%)
```

### 2c. Existing `ferrous_iron_yield` column

The existing `ferrous_iron_yield` column on `ScalarResults` is currently a manual-entry placeholder (unused in calculations, has a TODO). **Decision needed:**

- **Option A — Deprecate:** Mark `ferrous_iron_yield` as deprecated. Keep the column for backwards compatibility but stop exposing it in new UI/templates. The two new specific columns replace its intent.
- **Option B — Repurpose:** Rename to one of the new columns via migration. This is riskier for existing data.

**Recommendation:** Option A — deprecate in place. The two new columns are explicitly named and unambiguous.

### 2d. Alembic Migration

A migration will be auto-generated per project convention (`alembic revision --autogenerate`). The migration adds:
- `total_ferrous_iron` to `experimental_conditions`
- `ferrous_iron_yield_h2_pct` to `scalar_results`
- `ferrous_iron_yield_nh3_pct` to `scalar_results`

The PowerBI view in `event_listeners.py` must also be updated to expose the two new columns (see Section 5).

---

## 3. Calculation Logic

### 3a. Location

All logic goes inside `ScalarResults.calculate_yields()` in `database/models/results.py`, replacing the existing TODO block at the end of that method.

### 3b. H₂-Derived Calculation

```python
FE_MOLAR_MASS = 55.845  # g/mol

total_ferrous_iron = self.result_entry.experiment.conditions.total_ferrous_iron

# H2-derived ferrous iron yield
if (self.h2_micromoles is not None
        and total_ferrous_iron is not None
        and total_ferrous_iron > 0):
    fe2_consumed_umol = self.h2_micromoles * 3  # 3 mol Fe2+ per 1 mol H2
    fe2_consumed_g = (fe2_consumed_umol / 1_000_000) * FE_MOLAR_MASS
    self.ferrous_iron_yield_h2_pct = (fe2_consumed_g / total_ferrous_iron) * 100
else:
    self.ferrous_iron_yield_h2_pct = None
```

### 3c. NH₃-Derived Calculation

```python
# NH3-derived ferrous iron yield
if (self.gross_ammonium_concentration_mM is not None
        and liquid_volume_ml is not None
        and liquid_volume_ml > 0
        and total_ferrous_iron is not None
        and total_ferrous_iron > 0):
    bg_conc = (self.background_ammonium_concentration_mM
               if self.background_ammonium_concentration_mM is not None else 0.3)
    net_conc = max(0.0, self.gross_ammonium_concentration_mM - bg_conc)
    total_nh3_mol = (net_conc / 1000) * (liquid_volume_ml / 1000)
    fe2_consumed_mol = total_nh3_mol * (9 / 2)  # 9 mol Fe2+ per 2 mol NH3
    fe2_consumed_g = fe2_consumed_mol * FE_MOLAR_MASS
    self.ferrous_iron_yield_nh3_pct = (fe2_consumed_g / total_ferrous_iron) * 100
else:
    self.ferrous_iron_yield_nh3_pct = None
```

**Note:** `liquid_volume_ml` is already resolved earlier in `calculate_yields()` (prefers `sampling_volume_mL`, falls back to `water_volume_mL` from conditions). Reuse that same variable — do not duplicate the resolution logic.

### 3d. Guard Clauses

Both calculations must be skipped (set to `None`) when:
- `total_ferrous_iron` is `None` or `<= 0`
- The respective product measurement is missing (`h2_micromoles` for H₂-derived; `gross_ammonium_concentration_mM` for NH₃-derived)
- `liquid_volume_ml` is missing for the NH₃ path

### 3e. Recalculation Triggers

The existing architecture already re-runs `calculate_yields()` in these scenarios:
- **Scalar data save** — `frontend/components/experimental_results.py` calls `scalar_entry.calculate_yields()` on create/update
- **Conditions change** — `backend/services/experimental_conditions_service.py` refreshes scalar yields when conditions are modified
- **Backfill** — `frontend/components/utils.py` → `backfill_calculated_fields()` iterates all scalars

**New trigger needed:** When `total_ferrous_iron` is updated on conditions, all associated scalar results must be recalculated. This is already handled by the existing conditions-change path in `experimental_conditions_service.py` — verify it touches `calculate_yields()` for linked scalars.

---

## 4. Configuration & UI Changes

### 4a. `variable_config.py` — Conditions Field

Add to `FIELD_CONFIG`:

```python
'total_ferrous_iron': {
    'label': "Total Ferrous Iron (g)",
    'type': 'number',
    'default': None,
    'min_value': 0.0,
    'step': 0.001,
    'format': "%.3f",
    'required': False,
    'help': "Total initial ferrous iron (Fe²⁺) mass in grams for yield calculations."
},
```

### 4b. `variable_config.py` — Scalar Results Fields

Add to `SCALAR_RESULTS_CONFIG`:

```python
'ferrous_iron_yield_h2_pct': {
    'label': "Ferrous Iron Yield (%) (H₂ Derived)",
    'type': 'number',
    'default': None,
    'min_value': 0.0,
    'max_value': None,
    'step': 0.01,
    'format': "%.2f",
    'required': False,
    'readonly': True,
    'help': "Calculated: Fe²⁺ yield based on H₂ generation (3 mol Fe²⁺ per mol H₂)."
},
'ferrous_iron_yield_nh3_pct': {
    'label': "Ferrous Iron Yield (%) (NH₃ Derived)",
    'type': 'number',
    'default': None,
    'min_value': 0.0,
    'max_value': None,
    'step': 0.01,
    'format': "%.2f",
    'required': False,
    'readonly': True,
    'help': "Calculated: Fe²⁺ yield based on NH₃ generation (9 mol Fe²⁺ per 2 mol NH₃)."
},
```

### 4c. Deprecate Existing `ferrous_iron_yield` Config

Update the existing `ferrous_iron_yield` entry in `SCALAR_RESULTS_CONFIG`:
- Add `'deprecated': True` or add a deprecation note in the help text
- Consider hiding from forms while keeping for backwards data compatibility

### 4d. `SCALAR_RESULTS_TEMPLATE_HEADERS`

Add mapping entries for the new fields (readonly/calculated fields are typically excluded from upload templates, but should appear in export views):

```python
"ferrous_iron_yield_h2_pct": "Fe2+ Yield H2 (%)",
"ferrous_iron_yield_nh3_pct": "Fe2+ Yield NH3 (%)",
```

Also add `total_ferrous_iron` to the conditions template headers if an equivalent mapping exists.

---

## 5. PowerBI View / Event Listener

### `database/event_listeners.py`

The flattened SQL view must include the two new scalar columns. Add after the existing `ferrous_iron_yield` line:

```sql
sr.ferrous_iron_yield_h2_pct AS ferrous_iron_yield_h2_pct,
sr.ferrous_iron_yield_nh3_pct AS ferrous_iron_yield_nh3_pct,
```

Also add `total_ferrous_iron` from the conditions join:

```sql
ec.total_ferrous_iron AS total_ferrous_iron,
```

**Note:** Any migration that recreates this view must include both the old and new columns.

---

## 6. Bulk Upload & Service Layer

### 6a. `backend/services/scalar_results_service.py`

Add both new fields to `SCALAR_UPDATABLE_FIELDS` list (even though they are calculated, the service needs to persist them):

```python
'ferrous_iron_yield_h2_pct', 'ferrous_iron_yield_nh3_pct',
```

### 6b. `backend/services/bulk_uploads/scalar_results.py`

Add column alias mappings if exposing through bulk upload ingestion.

### 6c. `backend/services/bulk_uploads/metric_groups.py`

Add metric group entries for the new fields if they should appear in metric-based views/exports.

### 6d. `frontend/components/bulk_uploads.py`

Update the scalar results Excel template to include the new columns (as readonly/calculated display columns, or exclude from upload input and only show on export).

---

## 7. Data Migration (Backfill)

Create a data migration script under `database/data_migrations/` following the existing pattern (e.g., `recalculate_ferrous_iron_yields_0XX.py`):

1. Query all `ScalarResults` joined to `ExperimentalConditions`
2. For each row where `total_ferrous_iron` is set, run the two calculations
3. Bulk update the new columns

Alternatively, leverage the existing `backfill_calculated_fields()` in `frontend/components/utils.py` — it already iterates all scalar results and calls `calculate_yields()`. After deploying the code changes, running the backfill should populate the new fields for any experiments that already have `total_ferrous_iron` set.

---

## 8. Files to Modify (Summary)

| File | Change |
|------|--------|
| `database/models/conditions.py` | Add `total_ferrous_iron` column |
| `database/models/results.py` | Add 2 new columns, implement calculation in `calculate_yields()` |
| `frontend/config/variable_config.py` | Add config entries for 3 new fields, deprecate old `ferrous_iron_yield` |
| `database/event_listeners.py` | Update PowerBI view SQL with new columns |
| `backend/services/scalar_results_service.py` | Add new fields to `SCALAR_UPDATABLE_FIELDS` |
| `backend/services/bulk_uploads/scalar_results.py` | Add column alias mappings |
| `backend/services/bulk_uploads/metric_groups.py` | Add metric group entries |
| `frontend/components/bulk_uploads.py` | Update Excel template |
| `frontend/components/experimental_results.py` | No change needed (already calls `calculate_yields()`) |
| `backend/services/experimental_conditions_service.py` | Verify recalc triggers on conditions change |
| `frontend/components/utils.py` | Verify `backfill_calculated_fields()` covers new fields |

---

## 9. Testing Checklist

- [ ] H₂-derived yield: 1000 µmol H₂ with 1.0 g total_ferrous_iron → (0.003 × 55.845 / 1.0) × 100 = **16.75%**
- [ ] NH₃-derived yield: 10 mM net ammonium in 100 mL with 1.0 g total_ferrous_iron → 0.001 mol NH₃ × 4.5 × 55.845 / 1.0 × 100 = **25.13%**
- [ ] Both fields are `None` when `total_ferrous_iron` is not set
- [ ] H₂ field is `None` when `h2_micromoles` is not available
- [ ] NH₃ field is `None` when ammonium concentration or solution volume is missing
- [ ] Updating `total_ferrous_iron` on conditions recalculates linked scalar results
- [ ] PowerBI view exposes new columns
- [ ] Bulk upload template reflects changes
- [ ] Backfill populates existing records correctly
