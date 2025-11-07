from __future__ import annotations

import io
from typing import Dict, List, Tuple, Optional, Any

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import (
    Experiment,
    ExperimentNotes,
    ExperimentalConditions,
    ChemicalAdditive,
    Compound,
    ExperimentStatus,
    AmountUnit,
)
from backend.services.bulk_uploads.chemical_inventory import ChemicalInventoryService
from backend.services.experiment_validation import parse_experiment_id, validate_experiment_id


class NewExperimentsUploadService:
    @staticmethod
    def bulk_upsert_from_excel(db: Session, file_bytes: bytes) -> Tuple[int, int, int, List[str], List[str]]:
        """
        Create or update Experiments, ExperimentalConditions, and ChemicalAdditives from a
        multi-sheet Excel workbook.

        Sheets (case-insensitive names):
          - experiments: experiment_id*, sample_id, date, status, initial_note, overwrite
            (researcher is optional and auto-populated from experiment_id if not provided)
          - conditions: experiment_id*, columns matching ExperimentalConditions fields
            (experiment_type is auto-populated from experiment_id)
          - additives: experiment_id*, compound*, amount*, unit*, order, method
          
        Experiment ID format: ExperimentType_ResearcherInitials_Index (e.g., Serum_MH_101)
        - Sequential: add -NUMBER (e.g., Serum_MH_101-2)
        - Treatment: add _TEXT (e.g., Serum_MH_101_Desorption)

        Overwrite behavior per experiment row:
          - overwrite=False and experiment exists: skip with error
          - overwrite=True and experiment exists: update provided fields; if additives sheet has
            rows for that experiment, REPLACE all existing additives with the provided set.

        Returns (created_experiments, updated_experiments, skipped_rows, errors, warnings)
        """
        created_exp = updated_exp = skipped = 0
        errors: List[str] = []
        warnings: List[str] = []

        try:
            sheets: Dict[str, pd.DataFrame] = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None)
        except Exception as e:
            return 0, 0, 0, [f"Failed to read Excel: {e}"], []

        # Normalize sheet keys
        normalized: Dict[str, pd.DataFrame] = {str(k).strip().lower(): v for k, v in (sheets or {}).items()}

        # Compounds sheet is no longer supported in this uploader; compounds can be bulked via the separate Chemical Inventory upload.

        # Helper: map enum for ExperimentStatus (accept name or value, case-insensitive)
        def parse_status(val: Any) -> Optional[ExperimentStatus]:
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None
            text = str(val).strip()
            for s in ExperimentStatus:
                if text.lower() == s.name.lower() or text.lower() == str(s.value).lower():
                    return s
            return None

        # Helper: parse boolean-ish overwrite flag
        def parse_bool(val: Any) -> bool:
            if isinstance(val, bool):
                return val
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return False
            return str(val).strip().lower() in {"1", "true", "yes", "y"}

        # Preload experiment map and compute next experiment_number for new experiments
        # Note: SQLite ignores FOR UPDATE; we mirror existing pattern from UI creation flow
        last = db.query(Experiment).order_by(Experiment.experiment_number.desc()).first()
        next_experiment_number = 1 if last is None else int(last.experiment_number or 0) + 1

        # Track overwrite preference per experiment_id
        overwrite_by_exp_id: Dict[str, bool] = {}

        # === Process experiments sheet ===
        if 'experiments' in normalized:
            df_exp = normalized['experiments'].copy()
            # Strip any display asterisks from headers and normalize to lowercase
            df_exp.columns = [str(c).replace('*', '').strip().lower() for c in df_exp.columns]

            for idx, row in df_exp.iterrows():
                try:
                    exp_id = str(row.get('experiment_id') or '').strip()
                    if not exp_id:
                        skipped += 1
                        continue

                    # Validate experiment ID and collect warnings
                    is_valid, id_warnings = validate_experiment_id(exp_id)
                    if id_warnings:
                        for warning in id_warnings:
                            warnings.append(f"[experiments] Row {idx+2} ({exp_id}): {warning}")
                    
                    # Parse experiment_id to extract components
                    parsed = parse_experiment_id(exp_id)

                    overwrite_flag = parse_bool(row.get('overwrite'))
                    overwrite_by_exp_id[exp_id] = overwrite_flag

                    # Resolve existing experiment (ignore hyphens/underscores/spaces, case-insensitive)
                    exp_id_norm = ''.join(ch for ch in exp_id.lower() if ch not in ['-', '_', ' '])
                    experiment = db.query(Experiment).filter(
                        func.lower(
                            func.replace(
                                func.replace(
                                    func.replace(Experiment.experiment_id, '-', ''),
                                    '_', ''
                                ),
                                ' ', ''
                            )
                        ) == exp_id_norm
                    ).first()

                    # Parse fields
                    sample_id = str(row.get('sample_id').strip()) if isinstance(row.get('sample_id'), str) and row.get('sample_id').strip() != '' else None
                    # Auto-populate researcher from experiment_id if not provided
                    researcher = str(row.get('researcher').strip()) if isinstance(row.get('researcher'), str) and row.get('researcher').strip() != '' else None
                    if not researcher and parsed.researcher_initials:
                        researcher = parsed.researcher_initials
                    status_val = parse_status(row.get('status'))
                    # date can be Excel serial, ISO, or empty
                    date_val: Optional[pd.Timestamp]
                    try:
                        date_raw = row.get('date')
                        if pd.isna(date_raw):
                            date_val = None
                        else:
                            date_val = pd.to_datetime(date_raw, errors='coerce')
                    except Exception:
                        date_val = None
                    initial_note = str(row.get('initial_note')).strip() if row.get('initial_note') is not None and str(row.get('initial_note')).strip() != '' else None

                    if experiment is None and overwrite_flag:
                        # Overwrite requested but experiment does not exist
                        errors.append(f"[experiments] Row {idx+2}: overwrite=True but experiment_id '{exp_id}' does not exist")
                        continue

                    if experiment is not None and not overwrite_flag:
                        errors.append(f"[experiments] Row {idx+2}: experiment_id '{exp_id}' already exists; set overwrite=True to update")
                        continue

                    if experiment is None:
                        # Create new experiment
                        experiment = Experiment(
                            experiment_number=next_experiment_number,
                            experiment_id=exp_id,
                            sample_id=sample_id,
                            researcher=researcher,
                            status=status_val if status_val is not None else ExperimentStatus.ONGOING,
                            date=(None if date_val is None else date_val.to_pydatetime()),
                        )
                        db.add(experiment)
                        db.flush()
                        next_experiment_number += 1
                        created_exp += 1
                    else:
                        # Update provided fields only
                        if sample_id is not None:
                            experiment.sample_id = sample_id
                        if researcher is not None:
                            experiment.researcher = researcher
                        if status_val is not None:
                            experiment.status = status_val
                        if date_val is not None:
                            experiment.date = date_val.to_pydatetime()
                        updated_exp += 1

                    # Handle initial note: create new ExperimentNotes entry, do not overwrite existing
                    if initial_note:
                        note = ExperimentNotes(
                            experiment_fk=experiment.id,
                            experiment_id=experiment.experiment_id,
                            note_text=initial_note,
                        )
                        db.add(note)

                except Exception as e:
                    errors.append(f"[experiments] Row {idx+2}: {e}")
        else:
            errors.append("Missing required 'experiments' sheet")

        # === Process conditions sheet (optional but recommended) ===
        if 'conditions' in normalized:
            df_cond = normalized['conditions'].copy()
            # Strip any display asterisks from headers and normalize
            df_cond.columns = [str(c).replace('*', '').strip().lower() for c in df_cond.columns]
            if 'experiment_id' not in df_cond.columns:
                errors.append("[conditions] Missing required column 'experiment_id'")
            else:
                # Build set of updatable attribute names from the model (avoid PK/FKs and internals)
                reserved = {'id', 'experiment_id', 'experiment_fk', 'created_at', 'updated_at'}
                blacklist = {
                    'catalyst', 'catalyst_mass',
                    'buffer_system', 'buffer_concentration',
                    'surfactant_type', 'surfactant_concentration',
                    'catalyst_percentage', 'catalyst_ppm',
                    'water_to_rock_ratio', 'nitrate_concentration', 'dissolved_oxygen',
                    'ammonium_chloride_concentration'   # Calculated field
                }
                updatable_attrs = {
                    col.name for col in ExperimentalConditions.__table__.columns
                    if col.name not in reserved and col.name not in blacklist
                }
                for idx, row in df_cond.iterrows():
                    try:
                        exp_id = str(row.get('experiment_id') or '').strip()
                        if not exp_id:
                            skipped += 1
                            continue
                        exp_id_norm = ''.join(ch for ch in exp_id.lower() if ch not in ['-', '_', ' '])
                        experiment = db.query(Experiment).filter(
                            func.lower(
                                func.replace(
                                    func.replace(
                                        func.replace(Experiment.experiment_id, '-', ''),
                                        '_', ''
                                    ),
                                    ' ', ''
                                )
                            ) == exp_id_norm
                        ).first()
                        if not experiment:
                            errors.append(f"[conditions] Row {idx+2}: experiment_id '{exp_id}' not found")
                            continue
                        # Resolve or create conditions
                        conditions = (
                            db.query(ExperimentalConditions)
                            .filter(ExperimentalConditions.experiment_fk == experiment.id)
                            .first()
                        )
                        if not conditions:
                            conditions = ExperimentalConditions(
                                experiment_id=experiment.experiment_id,
                                experiment_fk=experiment.id,
                            )
                            db.add(conditions)
                            db.flush()

                        # Apply updates for provided columns only
                        for col_name, val in row.items():
                            if col_name in updatable_attrs:
                                # Convert empty strings to None
                                if isinstance(val, str) and val.strip() == '':
                                    setattr(conditions, col_name, None)
                                else:
                                    try:
                                        setattr(conditions, col_name, val)
                                    except Exception:
                                        # Ignore unknown/invalid assignments silently
                                        pass
                        
                        # Auto-populate experiment_type from experiment_id if not already set
                        if not conditions.experiment_type or conditions.experiment_type == '':
                            parsed = parse_experiment_id(exp_id)
                            if parsed.experiment_type:
                                conditions.experiment_type = parsed.experiment_type.value
                        
                        # Recalculate derived fields
                        conditions.calculate_derived_conditions()
                    except Exception as e:
                        errors.append(f"[conditions] Row {idx+2}: {e}")

        # === Process additives sheet ===
        if 'additives' in normalized:
            df_add = normalized['additives'].copy()
            # Strip any display asterisks from headers and normalize
            df_add.columns = [str(c).replace('*', '').strip().lower() for c in df_add.columns]
            required_cols = {'experiment_id', 'compound', 'amount', 'unit'}
            if not required_cols.issubset(set(df_add.columns)):
                missing = ', '.join(sorted(required_cols - set(df_add.columns)))
                errors.append(f"[additives] Missing required column(s): {missing}")
            else:
                # Preload compounds into map; refresh as we auto-create
                all_compounds = db.query(Compound).all()
                name_to_compound: Dict[str, Compound] = {c.name.lower(): c for c in all_compounds}

                # Group rows by experiment_id for replace semantics
                grouped = df_add.groupby(df_add['experiment_id'].map(lambda x: str(x).strip()))
                for exp_id, group in grouped:
                    if not exp_id:
                        continue
                    exp_id_norm = ''.join(ch for ch in exp_id.lower() if ch not in ['-', '_', ' '])
                    experiment = db.query(Experiment).filter(
                        func.lower(
                            func.replace(
                                func.replace(
                                    func.replace(Experiment.experiment_id, '-', ''),
                                    '_', ''
                                ),
                                ' ', ''
                            )
                        ) == exp_id_norm
                    ).first()
                    if not experiment:
                        # Accumulate error per group header
                        errors.append(f"[additives] experiment_id '{exp_id}' not found")
                        continue

                    # Resolve or create conditions row
                    conditions = (
                        db.query(ExperimentalConditions)
                        .filter(ExperimentalConditions.experiment_fk == experiment.id)
                        .first()
                    )
                    if not conditions:
                        conditions = ExperimentalConditions(
                            experiment_id=experiment.experiment_id,
                            experiment_fk=experiment.id,
                        )
                        db.add(conditions)
                        db.flush()

                    replace_all = bool(overwrite_by_exp_id.get(exp_id, False))
                    if replace_all:
                        # Delete all existing additives for this experiment's conditions
                        db.query(ChemicalAdditive).filter(
                            ChemicalAdditive.experiment_id == conditions.id
                        ).delete(synchronize_session=False)

                    for ridx, row in group.iterrows():
                        try:
                            comp_name = str(row.get('compound') or '').strip()
                            if not comp_name:
                                skipped += 1
                                continue

                            # amount
                            try:
                                amount_val = float(row.get('amount'))
                            except Exception:
                                errors.append(f"[additives] Row {int(ridx)+2}: invalid amount '{row.get('amount')}'")
                                continue
                            if amount_val <= 0:
                                errors.append(f"[additives] Row {int(ridx)+2}: amount must be > 0")
                                continue

                            # unit
                            unit_text = str(row.get('unit') or '').strip()
                            unit_enum: Optional[AmountUnit] = None
                            for u in AmountUnit:
                                if unit_text == u.value:
                                    unit_enum = u
                                    break
                            if unit_enum is None:
                                errors.append(f"[additives] Row {int(ridx)+2}: invalid unit '{unit_text}'")
                                continue

                            # Resolve or auto-create compound by name
                            comp = name_to_compound.get(comp_name.lower())
                            if not comp:
                                comp = Compound(name=comp_name)
                                db.add(comp)
                                db.flush()
                                name_to_compound[comp_name.lower()] = comp

                            # order and method
                            order_val = row.get('order') if 'order' in df_add.columns else None
                            try:
                                order_int = int(order_val) if order_val is not None and str(order_val).strip() != '' else None
                            except Exception:
                                order_int = None
                            method_text = str(row.get('method')).strip() if 'method' in df_add.columns and row.get('method') is not None and str(row.get('method')).strip() != '' else None

                            if replace_all:
                                # Always insert fresh records
                                new_add = ChemicalAdditive(
                                    experiment_id=conditions.id,
                                    compound_id=comp.id,
                                    amount=amount_val,
                                    unit=unit_enum,
                                    addition_order=order_int,
                                    addition_method=method_text,
                                )
                                # Derived fields auto via event listeners; call explicitly for safety
                                new_add.calculate_derived_values()
                                db.add(new_add)
                            else:
                                # Upsert per-compound
                                existing_add = db.query(ChemicalAdditive).filter(
                                    ChemicalAdditive.experiment_id == conditions.id,
                                    ChemicalAdditive.compound_id == comp.id,
                                ).first()
                                if existing_add:
                                    existing_add.amount = amount_val
                                    existing_add.unit = unit_enum
                                    existing_add.addition_order = order_int
                                    existing_add.addition_method = method_text
                                    existing_add.calculate_derived_values()
                                else:
                                    new_add = ChemicalAdditive(
                                        experiment_id=conditions.id,
                                        compound_id=comp.id,
                                        amount=amount_val,
                                        unit=unit_enum,
                                        addition_order=order_int,
                                        addition_method=method_text,
                                    )
                                    new_add.calculate_derived_values()
                                    db.add(new_add)
                        except Exception as e:
                            errors.append(f"[additives] Row {int(ridx)+2}: {e}")

        return created_exp, updated_exp, skipped, errors, warnings


