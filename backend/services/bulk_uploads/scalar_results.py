from __future__ import annotations

import io
from typing import List, Tuple, Dict, Any, Optional
import math
import datetime as dt

import pandas as pd
from sqlalchemy.orm import Session

from backend.services.scalar_results_service import ScalarResultsService
from frontend.config.variable_config import SCALAR_RESULTS_TEMPLATE_HEADERS


class ScalarResultsUploadService:
    @staticmethod
    def _parse_measurement_date(value: Any) -> Optional[dt.datetime]:
        """
        Normalize measurement_date to a Python datetime for SQLite DateTime columns.

        Accepts pandas Timestamp, datetime/date, or string-like values.
        Returns None if the value is empty/invalid.
        """
        if value is None:
            return None
        if isinstance(value, dt.datetime):
            return value
        if isinstance(value, dt.date):
            return dt.datetime.combine(value, dt.time.min)
        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime()
        if isinstance(value, str):
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.isna(parsed):
                return None
            return parsed.to_pydatetime()
        # Try pandas as a last resort (handles numeric Excel dates)
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()

    @staticmethod
    def bulk_upsert_from_excel(db: Session, file_bytes: bytes, overwrite_all: bool = False) -> Tuple[int, int, int, List[str]]:
        """
        Parse the Solution Chemistry Excel and delegate creation/upsert to ScalarResultsService.
        
        Args:
            db: Database session
            file_bytes: Excel file bytes
            overwrite_all: If True, replace all fields for existing records. 
                          Per-row 'overwrite' column takes precedence.
        
        Returns (created, updated, skipped, errors). Updated count is best-effort (service may overwrite in place).
        """
        errors: List[str] = []
        created = updated = skipped = 0

        try:
            # Use ExcelFile to inspect sheet names and find the data sheet
            xls = pd.ExcelFile(io.BytesIO(file_bytes))
            
            target_sheet = None
            
            # Priority 1: Look for the standard sheet name
            if "Solution Chemistry" in xls.sheet_names:
                target_sheet = "Solution Chemistry"
            
            # Priority 2: Look for any sheet that isn't the instructions sheet
            if target_sheet is None:
                for sheet in xls.sheet_names:
                    if "INSTRUCTION" not in sheet.upper():
                        target_sheet = sheet
                        break
            
            # Priority 3: Default to the first sheet if we can't determine otherwise
            if target_sheet is None and xls.sheet_names:
                target_sheet = 0
            
            df = pd.read_excel(xls, sheet_name=target_sheet)
        except Exception as e:
            return 0, 0, 0, [f"Failed to read Excel: {e}"]

        # Remove any asterisks used to mark required columns in UI templates
        df.columns = [str(c).replace('*', '') for c in df.columns]

        # Rename English headers to variable names using config mapping
        # Create reverse mapping: English Header -> variable_name
        header_map = {v: k for k, v in SCALAR_RESULTS_TEMPLATE_HEADERS.items()}
        
        new_columns = []
        for col in df.columns:
            col_str = str(col).strip()
            # Map English header to variable name if it matches
            if col_str in header_map:
                new_columns.append(header_map[col_str])
            else:
                # Keep original column name (allows backward compatibility with variable names)
                new_columns.append(col_str)
        
        df.columns = new_columns

        # Normalize empty cells: convert NaN to None and drop empty strings
        records: List[Dict[str, Any]] = df.to_dict('records')
        cleaned_records: List[Dict[str, Any]] = []
        for row_index, rec in enumerate(records):
            clean: Dict[str, Any] = {}
            for k, v in rec.items():
                # Strip asterisks handled above; treat NaN/blank as missing
                if v is None:
                    continue
                if isinstance(v, float) and math.isnan(v):
                    continue
                if isinstance(v, str) and v.strip() == '':
                    continue
                clean[k] = v

            if "measurement_date" in clean:
                parsed_date = ScalarResultsUploadService._parse_measurement_date(clean.get("measurement_date"))
                if parsed_date is None:
                    errors.append(f"Row {row_index + 2}: Invalid measurement_date (expected date/datetime).")
                    continue
                clean["measurement_date"] = parsed_date
            
            # Validate time_post_reaction is present and numeric
            time_val = clean.get('time_post_reaction')
            if time_val is None:
                errors.append(
                    f"Row {row_index + 2}: 'Time (days)' is required. "
                    f"Use 0 for pre-reaction baselines."
                )
                continue
            try:
                clean['time_post_reaction'] = float(time_val)
            except (ValueError, TypeError):
                errors.append(
                    f"Row {row_index + 2}: 'Time (days)' must be a number, got '{time_val}'."
                )
                continue

            # Handle per-row overwrite flag: per-row takes precedence over global
            row_overwrite = clean.pop('overwrite', None)
            if row_overwrite is not None:
                # Convert to boolean if needed
                if isinstance(row_overwrite, str):
                    clean['_overwrite'] = row_overwrite.lower() in ('true', '1', 'yes')
                else:
                    clean['_overwrite'] = bool(row_overwrite)
            else:
                clean['_overwrite'] = overwrite_all
            
            cleaned_records.append(clean)

        # Delegate to service
        try:
            results, svc_errors = ScalarResultsService.bulk_create_scalar_results(db, cleaned_records)
            errors.extend(svc_errors)
            created = len(results) if results else 0
        except Exception as e:
            errors.append(str(e))

        return created, updated, skipped, errors


