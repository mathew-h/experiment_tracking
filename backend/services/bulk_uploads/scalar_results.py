from __future__ import annotations

import io
from typing import List, Tuple, Dict, Any
import math

import pandas as pd
from sqlalchemy.orm import Session

from backend.services.scalar_results_service import ScalarResultsService


class ScalarResultsUploadService:
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

        # Normalize empty cells: convert NaN to None and drop empty strings
        records: List[Dict[str, Any]] = df.to_dict('records')
        cleaned_records: List[Dict[str, Any]] = []
        for rec in records:
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


