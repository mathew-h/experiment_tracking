import io
import pandas as pd
import datetime as dt
from typing import Tuple, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from backend.services.scalar_results_service import ScalarResultsService

class MasterBulkUploadService:
    @staticmethod
    def _parse_date(value: Any) -> dt.datetime | None:
        if pd.isna(value) or value is None:
            return None
        
        if isinstance(value, str):
            if "1/0/1900" in value or value.strip() == "":
                return None
            try:
                parsed = pd.to_datetime(value, errors="coerce")
                if pd.isna(parsed):
                    return None
                if parsed.year <= 1900:
                    return None
                return parsed.to_pydatetime()
            except Exception:
                return None
        
        if isinstance(value, dt.datetime):
            if value.year <= 1900:
                return None
            return value
            
        if isinstance(value, dt.date):
            if value.year <= 1900:
                return None
            return dt.datetime.combine(value, dt.time.min)
            
        if isinstance(value, pd.Timestamp):
            if value.year <= 1900:
                return None
            return value.to_pydatetime()
            
        try:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.isna(parsed) or parsed.year <= 1900:
                return None
            return parsed.to_pydatetime()
        except Exception:
            return None

    @staticmethod
    def _parse_numeric(value: Any) -> float | None:
        if pd.isna(value) or value is None:
            return None
        if isinstance(value, str):
            if "#DIV/0!" in value or value.strip() == "":
                return None
            try:
                return float(value.replace(",", ""))
            except ValueError:
                return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def parse_file(file_bytes: bytes) -> List[Dict[str, Any]]:
        try:
            try:
                df = pd.read_csv(io.BytesIO(file_bytes))
            except Exception:
                xls = pd.ExcelFile(io.BytesIO(file_bytes))
                if 'Dashboard' in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name='Dashboard')
                elif len(xls.sheet_names) == 1:
                    df = pd.read_excel(xls, sheet_name=0)
                else:
                    raise ValueError("The Excel file has multiple sheets, but no sheet named 'Dashboard' was found. Please ensure the data is in the 'Dashboard' sheet.")
            
            df.columns = [str(c).strip() for c in df.columns]
            return df.to_dict('records')
        except Exception as e:
            raise ValueError(f"Failed to read file: {str(e)}")

    @staticmethod
    def bulk_upsert(
        db: Session,
        file_bytes: bytes,
        dry_run: bool = False
    ) -> Tuple[int, int, int, List[str], List[Dict[str, Any]]]:
        """
        Processes Master Bulk Upload CSV/Excel.
        Returns: created, updated, skipped, errors, feedbacks
        """
        created = 0
        updated = 0
        skipped = 0
        errors = []
        feedbacks = []
        
        try:
            records = MasterBulkUploadService.parse_file(file_bytes)
        except Exception as e:
            errors.append(str(e))
            return 0, 0, 0, errors, []
            
        cleaned_records = []
        parse_feedbacks = []
        
        for idx, row in enumerate(records):
            row_num = idx + 2 # Assuming header is row 1
            
            exp_id = row.get("Experiment ID")
            if pd.isna(exp_id) or not str(exp_id).strip():
                errors.append(f"Row {row_num}: Missing 'Experiment ID'. Skipping.")
                skipped += 1
                continue
            
            exp_id = str(exp_id).strip()
            
            duration_val = MasterBulkUploadService._parse_numeric(row.get("Duration (Days)"))
            if duration_val is None:
                errors.append(f"Row {row_num}: Missing or invalid 'Duration (Days)'. Skipping.")
                skipped += 1
                continue
                
            clean_row = {
                "experiment_id": exp_id,
                "time_post_reaction": duration_val,
            }
            
            desc = row.get("Description")
            if not pd.isna(desc) and desc is not None:
                clean_row["description"] = str(desc).strip()
                
            sample_date = MasterBulkUploadService._parse_date(row.get("Sample Date"))
            if sample_date:
                clean_row["measurement_date"] = sample_date
                
            nmr_date = MasterBulkUploadService._parse_date(row.get("NMR Run Date"))
            if nmr_date:
                clean_row["nmr_run_date"] = nmr_date
                
            icp_date = MasterBulkUploadService._parse_date(row.get("ICP Run Date"))
            if icp_date:
                clean_row["icp_run_date"] = icp_date
                
            gc_date = MasterBulkUploadService._parse_date(row.get("GC Run Date"))
            if gc_date:
                clean_row["gc_run_date"] = gc_date
                
            nh4_mm = MasterBulkUploadService._parse_numeric(row.get("NH4 (mM)"))
            if nh4_mm is not None:
                clean_row["gross_ammonium_concentration_mM"] = nh4_mm
                
            h2_ppm = MasterBulkUploadService._parse_numeric(row.get("H2 (ppm)"))
            if h2_ppm is not None:
                clean_row["h2_concentration"] = h2_ppm
                clean_row["h2_concentration_unit"] = "ppm"
                
            gas_vol = MasterBulkUploadService._parse_numeric(row.get("Gas Volume (mL)"))
            if gas_vol is not None:
                clean_row["gas_sampling_volume_ml"] = gas_vol
                
            gas_pres_psi = MasterBulkUploadService._parse_numeric(row.get("Gas Pressure (psi)"))
            if gas_pres_psi is not None:
                # Convert psi to MPa
                clean_row["gas_sampling_pressure_MPa"] = gas_pres_psi * 0.00689476
                
            ph = MasterBulkUploadService._parse_numeric(row.get("Sample pH"))
            if ph is not None:
                clean_row["final_ph"] = ph
                
            cond = MasterBulkUploadService._parse_numeric(row.get("Sample Conductivity (mS/cm)"))
            if cond is not None:
                clean_row["final_conductivity_mS_cm"] = cond
                
            mod = row.get("Modification")
            if not pd.isna(mod) and mod is not None and str(mod).strip() != "0":
                clean_row["brine_modification_description"] = str(mod).strip()
                
            overwrite_val = row.get("Overwrite")
            overwrite = False
            if not pd.isna(overwrite_val):
                if isinstance(overwrite_val, bool):
                    overwrite = overwrite_val
                elif str(overwrite_val).strip().upper() == "TRUE":
                    overwrite = True
            
            clean_row["_overwrite"] = overwrite
            
            # Check if experiment and result already exist
            # This implements "If there are existing results, do not overwrite. ONLY OVERWRITE IF 'Overwrite' is TRUE."
            import backend.services.result_merge_utils as merge_utils
            
            exp = ScalarResultsService._find_experiment(db, exp_id)
            
            # If experiment exists, check if result exists
            if exp:
                existing_res = merge_utils.find_timepoint_candidates(db, exp.id, duration_val)
                if existing_res and not overwrite:
                    feedbacks.append({
                        "row": row_num,
                        "experiment_id": exp_id,
                        "time_post_reaction": duration_val,
                        "status": "skipped",
                        "fields_updated": [],
                        "fields_preserved": [],
                        "old_values": {},
                        "new_values": {},
                        "warnings": ["Existing result found and Overwrite is False."],
                        "errors": [],
                    })
                    skipped += 1
                    continue
            else:
                # If experiment_id does not exist, simply skip that row
                errors.append(f"Row {row_num}: Experiment '{exp_id}' not found. Skipping.")
                skipped += 1
                continue
            
            cleaned_records.append(clean_row)
            
        if dry_run:
            for idx, rec in enumerate(cleaned_records):
                row_num = idx + 2
                data_fields = sorted(
                    f for f in rec
                    if f not in ("_overwrite", "description", "time_post_reaction", "experiment_id", "measurement_date")
                    and rec.get(f) is not None
                )
                feedbacks.append({
                    "row": row_num,
                    "experiment_id": str(rec.get("experiment_id", "")),
                    "time_post_reaction": rec.get("time_post_reaction"),
                    "status": "dry_run",
                    "fields_updated": data_fields,
                    "fields_preserved": [],
                    "old_values": {}, "new_values": {},
                    "warnings": [],
                    "errors": [],
                })
            return 0, 0, skipped, errors, feedbacks

        res_created, svc_errors, svc_feedbacks = ScalarResultsService.bulk_create_scalar_results_ex(db, cleaned_records)
        errors.extend(svc_errors)
        
        for fb in svc_feedbacks:
            if fb["status"] == "created":
                created += 1
            elif fb["status"] == "updated":
                updated += 1
            elif fb["status"] in ("skipped", "error"):
                skipped += 1
                
        feedbacks.extend(svc_feedbacks)
        
        return created, updated, skipped, errors, feedbacks