from __future__ import annotations

import io
from typing import List, Tuple, Optional, Dict

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import SampleInfo, SamplePhotos, ExternalAnalysis
from database.models.analysis import PXRFReading
from utils.storage import save_file


class RockInventoryService:
    @staticmethod
    def _parse_bool(val) -> Optional[bool]:
        if val is None:
            return None
        s = str(val).strip().lower()
        if s in {"true", "yes", "1"}:
            return True
        if s in {"false", "no", "0"}:
            return False
        return None

    @staticmethod
    def bulk_upsert_samples(
        db: Session,
        file_bytes: bytes,
        image_files: List[Tuple[str, bytes, Optional[str]]],
    ) -> Tuple[int, int, int, int, List[str]]:
        """
        Upsert rock samples (SampleInfo) and attach photos.

        Args:
            db: SQLAlchemy session
            file_bytes: Excel file bytes containing sample rows
            image_files: list of tuples (file_name, file_bytes, mime_type)

        Returns:
            (created, updated, images_attached, skipped, errors)
        """
        created = updated = images_attached = skipped = 0
        errors: List[str] = []

        try:
            df = pd.read_excel(io.BytesIO(file_bytes))
        except Exception as e:
            return 0, 0, 0, 0, [f"Failed to read Excel: {e}"]

        # Normalize headers
        df.columns = [str(c).strip().lower() for c in df.columns]

        required = {"sample_id"}
        if not required.issubset(set(df.columns)):
            return 0, 0, 0, 0, ["Missing required column: sample_id"]

        # Optional fields aligned with SampleInfo
        field_map = {
            "rock_classification": "rock_classification",
            "state": "state",
            "country": "country",
            "locality": "locality",
            "latitude": "latitude",
            "longitude": "longitude",
            "description": "description",
            "characterized": "characterized",
            "overwrite": "overwrite",  # Special flag for full replacement mode
        }

        # Track samples in this batch by normalized ID to prevent duplicates
        seen_samples = {}

        for idx, row in df.iterrows():
            try:
                sample_id = str(row.get("sample_id") or "").strip()
                if not sample_id:
                    skipped += 1
                    continue

                # Normalize sample_id for matching: ignore hyphens/underscores/spaces, case-insensitive
                sid_norm = ''.join(ch for ch in sample_id.lower() if ch not in ['-', '_', ' '])
                
                # Check if we've already processed this sample in THIS batch
                if sid_norm in seen_samples:
                    sample = seen_samples[sid_norm]
                    is_new = False
                else:
                    # Find existing in database or create new
                    sample = db.query(SampleInfo).filter(
                        func.lower(
                            func.replace(
                                func.replace(
                                    func.replace(SampleInfo.sample_id, '-', ''),
                                    '_', ''
                                ),
                                ' ', ''
                            )
                        ) == sid_norm
                    ).first()
                    is_new = False
                    if not sample:
                        # Use original sample_id string for storage
                        sample = SampleInfo(sample_id=sample_id)
                        db.add(sample)
                        is_new = True
                    # Track this sample for the rest of the batch
                    seen_samples[sid_norm] = sample

                # Check overwrite mode
                overwrite_mode = False
                if 'overwrite' in df.columns:
                    overwrite_val = RockInventoryService._parse_bool(row.get('overwrite'))
                    overwrite_mode = overwrite_val is True

                # If overwrite mode and existing sample, clear all optional fields first
                if overwrite_mode and not is_new:
                    for attr in ["rock_classification", "state", "country", "locality", 
                                 "latitude", "longitude", "description", "characterized"]:
                        setattr(sample, attr, None)

                # Update fields if present
                for col, attr in field_map.items():
                    if col == "overwrite":
                        continue  # Skip the overwrite flag itself
                    if col in df.columns:
                        val = row.get(col)
                        if attr in {"latitude", "longitude"}:
                            try:
                                val = float(val) if val is not None and str(val).strip() != "" else None
                            except Exception:
                                val = None
                        elif attr == "characterized":
                            parsed = RockInventoryService._parse_bool(val)
                            val = parsed if parsed is not None else getattr(sample, attr)
                        # Allow None to clear only for non-PK
                        setattr(sample, attr, val)

                # Create ExternalAnalysis for pXRF if pxrf_reading_no column present
                if 'pxrf_reading_no' in df.columns:
                    try:
                        pxrf_val = row.get('pxrf_reading_no')
                        pxrf_str = str(pxrf_val).strip() if pxrf_val is not None else ''
                        if pxrf_str:
                            # Prevent duplicates
                            existing_ext = (
                                db.query(ExternalAnalysis)
                                .filter(
                                    ExternalAnalysis.sample_id == sample_id,
                                    ExternalAnalysis.analysis_type == 'pXRF',
                                    ExternalAnalysis.pxrf_reading_no == pxrf_str
                                )
                                .first()
                            )
                            if not existing_ext:
                                # Link only if the PXRFReading exists to satisfy FK; otherwise store as description
                                reading = db.query(PXRFReading).filter(PXRFReading.reading_no == pxrf_str).first()
                                if reading:
                                    db.add(ExternalAnalysis(
                                        sample_id=sample_id,
                                        analysis_type='pXRF',
                                        pxrf_reading_no=pxrf_str,
                                    ))
                                else:
                                    db.add(ExternalAnalysis(
                                        sample_id=sample_id,
                                        analysis_type='pXRF',
                                        description=f"pXRF reading no: {pxrf_str} (not found)",
                                    ))
                    except Exception as e:
                        errors.append(f"Row {idx+2}: failed to create pXRF link — {e}")

                if is_new:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                errors.append(f"Row {idx+2}: {e}")

        # Attach images: file name (without extension) should match a sample_id
        # Save to storage under sample_photos/{sample_id}
        if image_files:
            # Build existing photos lookup per (sample_id, file_name)
            for (file_name, data, mime_type) in image_files:
                try:
                    base_name = file_name.rsplit('/', 1)[-1]
                    simple_name = base_name.rsplit('\\', 1)[-1]
                    name_no_ext = simple_name.rsplit('.', 1)[0]
                    target_sample_id = name_no_ext.strip()
                    if not target_sample_id:
                        continue

                    sample = db.query(SampleInfo).filter(SampleInfo.sample_id == target_sample_id).first()
                    if not sample:
                        # Skip silently; sample might not be in this batch
                        continue

                    storage_folder = f"sample_photos/{target_sample_id}"
                    saved_path = save_file(data, simple_name, folder=storage_folder)
                    existing_photo = (
                        db.query(SamplePhotos)
                        .filter(SamplePhotos.sample_id == target_sample_id, SamplePhotos.file_name == simple_name)
                        .first()
                    )
                    if existing_photo:
                        existing_photo.file_path = saved_path
                        existing_photo.file_type = mime_type
                    else:
                        db.add(SamplePhotos(
                            sample_id=target_sample_id,
                            file_path=saved_path,
                            file_name=simple_name,
                            file_type=mime_type,
                        ))
                    images_attached += 1
                except Exception as e:
                    errors.append(f"Image '{file_name}': {e}")

        return created, updated, images_attached, skipped, errors


