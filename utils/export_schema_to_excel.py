"""
Export all database tables (from database.models) to a single Excel file with one
sheet per table. Each sheet contains a header row with all column names; optional
second row with SQL types. No data rows by default; use include_data=True to dump
current table contents.

Usage (from project root):
    python -m utils.export_schema_to_excel
    python -m utils.export_schema_to_excel --output my_schema.xlsx
    python -m utils.export_schema_to_excel --include-data
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# Add project root so "database" and "config" resolve
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pandas as pd
from sqlalchemy import text

# Import database so Base.metadata is populated with all models from database.models
from database import Base
from database.database import engine


# Excel sheet names: max 31 chars; cannot contain \ / * ? : [ ]
def _excel_sheet_name(table_name: str) -> str:
    invalid = re.compile(r'[\/*?:\[\]\\]')
    name = invalid.sub("_", table_name)
    return name[:31] if len(name) > 31 else name


def get_tables_from_metadata():
    """Return tables registered on Base.metadata (all models in database.models)."""
    return list(Base.metadata.tables.values())


def export_schema_to_excel(
    output_path: str | Path,
    include_data: bool = False,
    include_types: bool = True,
) -> None:
    """
    Write one Excel file with one sheet per table. Each sheet has:
    - Row 1: column names (headers)
    - Row 2 (optional): SQL type for each column
    - Remaining rows (optional): table data if include_data is True

    Parameters
    ----------
    output_path : str or Path
        Path to the output .xlsx file.
    include_data : bool
        If True, query each table and append rows to the sheet.
    include_types : bool
        If True, add a second header row with column types.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tables = get_tables_from_metadata()
    if not tables:
        raise RuntimeError("No tables found on Base.metadata. Ensure database.models are imported.")

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for table in tables:
            name = table.name
            sheet_name = _excel_sheet_name(name)
            columns = [c.name for c in table.c]
            type_map = {c.name: str(c.type) for c in table.c}

            if include_data:
                with engine.connect() as conn:
                    result = conn.execute(text(f'SELECT * FROM "{name}"'))
                    rows = result.fetchall()
                    result.close()
                df = pd.DataFrame(rows, columns=columns)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                if include_types:
                    ws = writer.sheets[sheet_name]
                    ws.insert_rows(2)
                    for col_idx, col_name in enumerate(columns, start=1):
                        ws.cell(row=2, column=col_idx, value=type_map.get(col_name, ""))
            else:
                df = pd.DataFrame(columns=columns)
                if include_types:
                    type_row = [type_map.get(c, "") for c in columns]
                    df.loc[0] = type_row
                df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"Wrote {len(tables)} sheets to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export database schema (and optionally data) to Excel.")
    parser.add_argument(
        "-o", "--output",
        default="database_schema.xlsx",
        help="Output Excel file path (default: database_schema.xlsx)",
    )
    parser.add_argument(
        "--include-data",
        action="store_true",
        help="Include current table data in each sheet",
    )
    parser.add_argument(
        "--no-types",
        action="store_true",
        help="Do not add a row with column types",
    )
    args = parser.parse_args()
    export_schema_to_excel(
        output_path=args.output,
        include_data=args.include_data,
        include_types=not args.no_types,
    )


if __name__ == "__main__":
    main()
