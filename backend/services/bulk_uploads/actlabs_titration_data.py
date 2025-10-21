from __future__ import annotations

import io
import math
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy.orm import Session

from database import Analyte, ElementalAnalysis, SampleInfo


class AnalyteService:
    @staticmethod
    def bulk_upsert_from_excel(db: Session, file_bytes: bytes) -> Tuple[int, int, int, List[str]]:
        """
        Upsert analyte definitions from an Excel file with columns: analyte_symbol*, unit*.
        Returns (created, updated, skipped, errors).
        """
        errors: List[str] = []
        created = updated = skipped = 0

        try:
            df = pd.read_excel(io.BytesIO(file_bytes))
        except Exception as e:
            return 0, 0, 0, [f"Failed to read Excel: {e}"]

        df.columns = [str(c).strip().lower() for c in df.columns]
        required = {"analyte_symbol", "unit"}
        if not required.issubset(set(df.columns)):
            return 0, 0, 0, [f"Missing required columns: {', '.join(sorted(required - set(df.columns)))}"]

        for idx, row in df.iterrows():
            try:
                symbol = str(row.get("analyte_symbol") or "").strip()
                unit = str(row.get("unit") or "").strip()
                if not symbol or not unit:
                    skipped += 1
                    continue

                existing = db.query(Analyte).filter(Analyte.analyte_symbol.ilike(symbol)).first()
                if existing:
                    existing.unit = unit
                    updated += 1
                else:
                    db.add(Analyte(analyte_symbol=symbol, unit=unit))
                    created += 1
            except Exception as e:
                errors.append(f"Row {idx+2}: {e}")

        return created, updated, skipped, errors


class ElementalCompositionService:
    @staticmethod
    def bulk_upsert_wide_from_excel(db: Session, file_bytes: bytes) -> Tuple[int, int, int, List[str]]:
        """
        Upsert ElementalAnalysis from a wide Excel file:
          - First column: sample_id
          - Remaining columns: analyte symbols
          - Cells: numeric composition
        Returns (created, updated, skipped_rows, errors).
        """
        errors: List[str] = []
        created = updated = skipped = 0

        try:
            df = pd.read_excel(io.BytesIO(file_bytes))
        except Exception as e:
            return 0, 0, 0, [f"Failed to read Excel: {e}"]

        df.columns = [str(c).strip() for c in df.columns]
        sample_col = None
        for c in df.columns:
            if c.lower() == "sample_id":
                sample_col = c
                break
        if not sample_col:
            return 0, 0, 0, ["First column must be 'sample_id'."]

        analyte_headers = [c for c in df.columns if c != sample_col]
        if not analyte_headers:
            return 0, 0, 0, ["No analyte columns detected."]

        all_analytes = db.query(Analyte).all()
        symbol_to_analyte = {a.analyte_symbol.lower(): a for a in all_analytes}

        for idx, row in df.iterrows():
            try:
                sample_id = str(row.get(sample_col) or '').strip()
                if not sample_id:
                    skipped += 1
                    continue

                # Ensure sample exists
                sample = db.query(SampleInfo).filter(SampleInfo.sample_id == sample_id).first()
                if not sample:
                    errors.append(f"Row {idx+2}: sample_id '{sample_id}' not found")
                    continue

                for symbol in analyte_headers:
                    analyte = symbol_to_analyte.get(str(symbol).lower())
                    if not analyte:
                        # Unknown analyte header; user should upload Analytes first
                        continue
                    val = row.get(symbol)
                    if val is None or (isinstance(val, float) and pd.isna(val)):
                        continue
                    try:
                        fval = float(val)
                    except Exception:
                        continue

                    existing = (
                        db.query(ElementalAnalysis)
                        .filter(ElementalAnalysis.sample_id == sample_id, ElementalAnalysis.analyte_id == analyte.id)
                        .first()
                    )
                    if existing:
                        existing.analyte_composition = fval
                        updated += 1
                    else:
                        db.add(ElementalAnalysis(sample_id=sample_id, analyte_id=analyte.id, analyte_composition=fval))
                        created += 1
            except Exception as e:
                errors.append(f"Row {idx+2}: {e}")

        return created, updated, skipped, errors


class ActlabsRockTitrationService:
    """Parser and importer for ActLabs rock titration files (Excel or CSV)."""

    @staticmethod
    def _read_table(file_bytes: bytes) -> Tuple[pd.DataFrame, Optional[str]]:
        """Try reading as Excel first, then CSV; always return a headerless table (header=None)."""
        try:
            df = pd.read_excel(io.BytesIO(file_bytes), header=None)
            return df, None
        except Exception:
            pass
        try:
            # Read CSV without headers
            df = pd.read_csv(io.BytesIO(file_bytes), header=None)
            return df, None
        except Exception as e:
            return pd.DataFrame(), f"Failed to read file as Excel or CSV: {e}"

    @staticmethod
    def _detect_sample_id_col(df_raw: pd.DataFrame) -> int:
        search_rows = min(6, len(df_raw))
        for c in range(df_raw.shape[1]):
            vals = df_raw.iloc[:search_rows, c].astype(str).str.lower().tolist()
            if any((("sample" in v and "id" in v) or v.strip() == "sample_id") for v in vals):
                return c
        return 0

    @staticmethod
    def _extract_last_analyte_map(df_raw: pd.DataFrame, sample_id_col: int) -> Dict[str, Tuple[int, Optional[str]]]:
        row3 = df_raw.iloc[2, :]  # Analyte Symbol
        row4 = df_raw.iloc[3, :]  # unit
        symbol_to_col_unit: Dict[str, Tuple[int, Optional[str]]] = {}
        for c in range(df_raw.shape[1]):
            if c == sample_id_col:
                continue
            symbol = row3[c]
            if pd.isna(symbol):
                continue
            sym = str(symbol).strip()
            if not sym:
                continue
            unit = None
            if c < len(row4):
                u = row4[c]
                unit = None if pd.isna(u) else str(u).strip() or None
            # Overwrite previous occurrence so the last column wins
            symbol_to_col_unit[sym] = (c, unit)
        return symbol_to_col_unit

    @staticmethod
    def _find_data_start_index(df_raw: pd.DataFrame) -> int:
        """Heuristically find the first data row index (after the header/meta rows).
        For ActLabs CSV, rows typically are:
          0: Report Number
          1: Report Date
          2: Analyte Symbol (headers row)
          3: Unit Symbol
          4: Detection Limit
          5: Analysis Method
          6+: data rows
        We prefer the row after 'Analysis Method'. Fallback to 4.
        """
        max_scan = min(12, len(df_raw))
        for i in range(max_scan):
            try:
                first_cell = str(df_raw.iat[i, 0]).strip().lower()
            except Exception:
                first_cell = ""
            if first_cell.startswith("analysis method"):
                return i + 1
        # Fallback to prior assumption (Excel layout)
        return 4

    @staticmethod
    def _coerce_number(x) -> Tuple[Optional[float], Optional[str]]:
        if pd.isna(x):
            return None, None
        sx = str(x).strip()
        if sx == "":
            return None, None
        if sx.lower() in {"nd", "na", "n/a"}:
            return None, sx
        try:
            val = float(sx)
            if math.isfinite(val):
                return val, None
        except ValueError:
            pass
        try:
            val2 = float(sx.lstrip("<>").strip())
            return val2, sx if sx and sx[0] in "<>" else sx
        except Exception:
            return None, sx

    @classmethod
    def import_excel(cls, db: Session, file_bytes: bytes) -> Tuple[int, int, int, List[str]]:
        """
        Import ActLabs Excel to normalized tables.
        - Upserts analytes (last header wins for units)
        - Upserts results per (sample_id, analyte_id)
        Returns (results_created, results_updated, skipped_rows, errors)
        """
        errors: List[str] = []
        results_created = results_updated = skipped = 0

        df_raw, read_err = cls._read_table(file_bytes)
        if read_err:
            return 0, 0, 0, [read_err]
        if df_raw.empty:
            return 0, 0, 0, ["No data found."]

        sample_id_col = cls._detect_sample_id_col(df_raw)
        symbol_to_col_unit = cls._extract_last_analyte_map(df_raw, sample_id_col)

        # Data rows typically start after the 'Analysis Method' row
        data_start = cls._find_data_start_index(df_raw)
        data = df_raw.iloc[data_start:, :].reset_index(drop=True)

        # Upsert analytes (last column wins for unit)
        for sym, (_c, unit) in symbol_to_col_unit.items():
            existing = db.query(Analyte).filter(Analyte.analyte_symbol.ilike(sym)).first()
            if existing:
                if unit:
                    existing.unit = unit
            else:
                db.add(Analyte(analyte_symbol=sym, unit=unit or "ppm"))

        # Preload analyte ids
        all_analytes = db.query(Analyte).all()
        symbol_to_analyte = {a.analyte_symbol.lower(): a for a in all_analytes}

        # Iterate rows
        for i in range(len(data)):
            sid_raw = data.iat[i, sample_id_col]
            if pd.isna(sid_raw):
                continue
            sample_id = str(sid_raw).strip()
            if not sample_id:
                continue
            # ensure sample exists
            sample = db.query(SampleInfo).filter(SampleInfo.sample_id == sample_id).first()
            if not sample:
                errors.append(f"Row {i+5}: sample_id '{sample_id}' not found")
                continue

            for sym, (col_idx, _unit) in symbol_to_col_unit.items():
                if col_idx >= data.shape[1]:
                    continue
                cell = data.iat[i, col_idx]
                vnum, _vtext = cls._coerce_number(cell)
                if vnum is None:
                    continue
                analyte = symbol_to_analyte.get(sym.lower())
                if not analyte:
                    # If misaligned, skip
                    continue
                existing = (
                    db.query(ElementalAnalysis)
                    .filter(ElementalAnalysis.sample_id == sample_id, ElementalAnalysis.analyte_id == analyte.id)
                    .first()
                )
                if existing:
                    existing.analyte_composition = vnum
                    results_updated += 1
                else:
                    db.add(ElementalAnalysis(sample_id=sample_id, analyte_id=analyte.id, analyte_composition=vnum))
                    results_created += 1

        return results_created, results_updated, skipped, errors


