from __future__ import annotations

from typing import List

import pandas as pd


def _is_nan(value: object) -> bool:
    """Return True if the provided value should be treated as missing/NaN."""
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def normalize_pxrf_token(token: str) -> str:
    """Normalize a single pXRF reading token (e.g., "12.0" -> "12")."""
    if token is None:
        return ""

    text = str(token).strip()
    if not text:
        return ""

    numeric_candidate = text.replace(".", "", 1).replace("-", "", 1)
    if numeric_candidate.isdigit():
        try:
            as_float = float(text)
            if as_float.is_integer():
                return str(int(as_float))
        except ValueError:
            pass

    return text


def normalize_pxrf_value(value: object) -> str:
    """Normalize a pXRF reading value that may contain comma-separated tokens."""
    if _is_nan(value):
        return ""

    text = str(value).strip()
    if not text:
        return ""

    if "," not in text:
        return normalize_pxrf_token(text)

    tokens = [
        normalize_pxrf_token(part)
        for part in text.split(",")
        if normalize_pxrf_token(part)
    ]
    return ",".join(tokens)


def split_normalized_pxrf_readings(value: object) -> List[str]:
    """Return a list of normalized pXRF reading numbers."""
    normalized = normalize_pxrf_value(value)
    if not normalized:
        return []
    return [token.strip() for token in normalized.split(",") if token.strip()]

