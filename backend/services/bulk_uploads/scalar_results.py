from __future__ import annotations

import io
from typing import List, Tuple, Dict, Any
import math

import pandas as pd
from sqlalchemy.orm import Session

from backend.services.scalar_results_service import ScalarResultsService


class ScalarResultsUploadService:
    @staticmethod
    def bulk_upsert_from_excel(db: Session, file_bytes: bytes) -> Tuple[int, int, int, List[str]]:
        """
        Parse the Solution Chemistry Excel and delegate creation/upsert to ScalarResultsService.
        Returns (created, updated, skipped, errors). Updated count is best-effort (service may overwrite in place).
        """
        errors: List[str] = []
        created = updated = skipped = 0

        try:
            df = pd.read_excel(io.BytesIO(file_bytes))
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
            cleaned_records.append(clean)

        # Delegate to service
        try:
            results, svc_errors = ScalarResultsService.bulk_create_scalar_results(db, cleaned_records)
            errors.extend(svc_errors)
            created = len(results) if results else 0
        except Exception as e:
            errors.append(str(e))

        return created, updated, skipped, errors


