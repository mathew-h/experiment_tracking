# pXRF Data Relationship Guide

## Overview
This document explains the relationship between pXRF readings, samples, and external analyses in the experiment tracking system.

## Database Schema

### 1. PXRFReading Table
**Location:** `database/models/analysis.py`

```python
class PXRFReading(Base):
    __tablename__ = "pxrf_readings"
    
    reading_no = Column(String, primary_key=True)  # e.g., "12345A", "1", "2"
    fe, mg, ni, cu, si, co, mo, al, ca, k, au = Column(Float, ...)
```

**Purpose:** Stores raw pXRF instrument readings with elemental composition data.

**Key Points:**
- `reading_no` is the primary key (stored as String)
- No foreign key relationships - this is a standalone lookup table
- Populated via bulk upload from pXRF instrument Excel exports
- Reading numbers can be any string format (numeric or alphanumeric)

### 2. SampleInfo Table
**Location:** `database/models/samples.py`

```python
class SampleInfo(Base):
    __tablename__ = "sample_info"
    
    sample_id = Column(String, primary_key=True)  # e.g., "ROCK-1", "MH027"
    rock_classification = Column(String)
    state, country, locality = ...
    
    # Relationships
    external_analyses = relationship("ExternalAnalysis", ...)
```

**Purpose:** Stores rock/sample inventory information.

**Key Points:**
- `sample_id` is the primary key (String)
- Contains location, classification, and description metadata
- Has one-to-many relationship with ExternalAnalysis

### 3. ExternalAnalysis Table (The Bridge)
**Location:** `database/models/analysis.py`

```python
class ExternalAnalysis(Base):
    __tablename__ = "external_analyses"
    
    id = Column(Integer, primary_key=True)
    sample_id = Column(String, ForeignKey("sample_info.sample_id"), ...)
    analysis_type = Column(String)  # e.g., "pXRF", "XRD", "Elemental"
    pxrf_reading_no = Column(String, nullable=True)  # Can store comma-separated values
    description = Column(Text)
    
    # Relationships
    sample_info = relationship("SampleInfo", back_populates="external_analyses")
```

**Purpose:** Links samples to their various external analyses, including pXRF readings.

**Key Points:**
- Acts as a bridge between samples and pXRF readings
- `pxrf_reading_no` is **NOT a foreign key** - it's a flexible String field
- Can store single reading numbers: `"12345A"`
- Can store comma-separated multiple readings: `"2,3,4"` or `"12345A,12346B"`
- No database-level constraint enforcement (intentional design for flexibility)

## Data Flow

### Uploading pXRF Readings

**Service:** `backend/services/bulk_uploads/pxrf_data.py` → `PXRFUploadService`

**Process:**
1. Upload Excel file from pXRF instrument
2. Extract `Reading No` column as the identifier
3. Normalize reading numbers (convert "1.0" → "1", trim whitespace)
4. Store elemental data (Fe, Mg, Ni, Cu, Si, Co, Mo, Al, Ca, K, Au)
5. Optionally update existing readings if checkbox enabled

**Excel Format:**
```
Reading No | Fe    | Mg    | Ni   | Cu   | ...
-----------|-------|-------|------|------|-----
1          | 45.2  | 12.3  | 0.5  | 0.2  | ...
2          | 43.1  | 11.8  | <LOD | 0.3  | ...
```

**Important Notes:**
- Reading numbers from Excel may come as floats (1.0, 2.0) → normalized to strings ("1", "2")
- NULL equivalents: `['', '<LOD', 'LOD', 'ND', 'n.d.', 'n/a', 'N/A', None]` → converted to 0

### Linking pXRF to Samples

**Service:** `backend/services/bulk_uploads/rock_inventory.py` → `RockInventoryService`

**Process:**
1. Upload rock inventory Excel with optional `pxrf_reading_no` column
2. For each sample row:
   - Upsert SampleInfo record
   - If `pxrf_reading_no` provided:
     - Normalize reading number(s) (handles "1.0" → "1", comma-separated lists)
     - Check if ExternalAnalysis already exists (prevent duplicates)
     - Validate each reading exists in PXRFReading table
     - Create ExternalAnalysis record linking sample to reading(s)

**Excel Format:**
```
sample_id  | rock_classification | pxrf_reading_no | ...
-----------|---------------------|-----------------|-----
ROCK-1     | Basalt              | 1               | ...
ROCK-2     | Granite             | 2,3,4           | ...
MH027      | Ultramafic          | 12345A          | ...
```

**Validation:**
- If reading number exists in PXRFReading → creates clean link
- If reading number NOT found → still creates link with warning message in description
- Comma-separated values supported: each reading is validated individually

## Common Scenarios

### Scenario 1: Single pXRF Reading per Sample
```
Sample: ROCK-1
pXRF Reading: 12345A

Result:
- SampleInfo: sample_id = "ROCK-1"
- ExternalAnalysis: sample_id = "ROCK-1", analysis_type = "pXRF", pxrf_reading_no = "12345A"
- PXRFReading: reading_no = "12345A" (with elemental data)
```

### Scenario 2: Multiple pXRF Readings per Sample
```
Sample: ROCK-2
pXRF Readings: 2, 3, 4 (multiple spots measured)

Result:
- SampleInfo: sample_id = "ROCK-2"
- ExternalAnalysis: sample_id = "ROCK-2", analysis_type = "pXRF", pxrf_reading_no = "2,3,4"
- PXRFReading: reading_no = "2" (with elemental data)
- PXRFReading: reading_no = "3" (with elemental data)
- PXRFReading: reading_no = "4" (with elemental data)
```

### Scenario 3: Reading Number Not Found
```
Sample: ROCK-3
pXRF Reading: 999 (not yet uploaded to PXRFReading table)

Result:
- SampleInfo: sample_id = "ROCK-3"
- ExternalAnalysis: 
    sample_id = "ROCK-3"
    analysis_type = "pXRF"
    pxrf_reading_no = "999"
    description = "pXRF reading(s): 999 (readings not found in database)"
- Warning logged in upload errors
```

## Troubleshooting

### Issue: Reading numbers don't match
**Symptom:** Uploaded reading "1.0" but rock inventory expects "1"

**Cause:** Excel stores integers as floats (1 becomes 1.0)

**Solution:** Both services now use `normalize_reading_number()` function to standardize format:
- Removes ".0" suffix from float strings
- Handles comma-separated lists
- Trims whitespace

**Code Reference:**
```python
def normalize_reading_number(val) -> str:
    # Converts "1.0" → "1", "2.0,3.0" → "2,3"
```

### Issue: Duplicate ExternalAnalysis records
**Symptom:** Multiple ExternalAnalysis records for same sample + reading combination

**Cause:** Re-uploading rock inventory without duplicate prevention

**Solution:** Service now checks for existing records before creating:
```python
existing_ext = db.query(ExternalAnalysis).filter(
    ExternalAnalysis.sample_id == sample.sample_id,
    ExternalAnalysis.analysis_type == 'pXRF',
    ExternalAnalysis.pxrf_reading_no == pxrf_str
).first()
```

### Issue: Sample ID formatting inconsistencies
**Symptom:** "ROCK-1", "rock-1", "ROCK_1", "ROCK 1" treated as different samples

**Cause:** Different input formats for the same sample

**Solution:** Service normalizes sample IDs:
- Convert to uppercase
- Remove spaces and underscores
- Preserve hyphens
- Match existing samples using normalized comparison
- Shows warning (not error) when format differs from existing

**Example:**
```
Input: "rock-1", "ROCK_1", "Rock 1"
Canonical: "ROCK-1"

If database has "ROCK_1", uploading "rock-1" will:
- Match the existing sample
- Update it (not create duplicate)
- Show warning: "Sample ID 'rock-1' normalized to 'ROCK-1', matches existing sample 'ROCK_1' - sample will be updated"
- Upload succeeds
```

**Note:** This is a warning, not an error - the upload will succeed and the sample will be properly updated.

### Issue: pXRF readings not visible in UI
**Symptom:** ExternalAnalysis records exist but data doesn't show

**Possible Causes:**
1. Frontend not querying ExternalAnalysis relationship
2. Reading numbers stored but PXRFReading data missing
3. Comma-separated readings not being parsed

**Solution:** Query pattern should be:
```python
sample = db.query(SampleInfo).filter(...).first()
pxrf_analyses = [a for a in sample.external_analyses if a.analysis_type == 'pXRF']
for analysis in pxrf_analyses:
    reading_nos = analysis.pxrf_reading_no.split(',')
    for reading_no in reading_nos:
        reading_data = db.query(PXRFReading).filter(PXRFReading.reading_no == reading_no.strip()).first()
```

## Best Practices

### 1. Upload Order
**Recommended sequence:**
1. Upload pXRF readings first (PXRFUploadService)
2. Then upload rock inventory with reading numbers (RockInventoryService)

**Rationale:** Ensures readings exist before linking to samples

### 2. Reading Number Formats
**Use consistent formats:**
- Numeric: "1", "2", "3" (not "1.0", "2.0")
- Alphanumeric: "12345A", "TEST-001"
- Comma-separated: "1,2,3" (no spaces after commas in Excel, but service handles both)

### 3. Overwrite Mode
**New feature:** Checkbox in UI for global overwrite behavior
- Unchecked (default): Only updates provided fields, preserves existing data
- Checked: Replaces ALL fields for existing samples
- Per-row 'overwrite' column in Excel takes precedence over checkbox

### 4. Error Handling and Warnings
**Service now separates errors from warnings:**

**Errors (block upload with rollback):**
- Excel file parsing failures
- Missing required columns
- Database constraint violations
- Unexpected exceptions

**Warnings (non-blocking, upload succeeds):**
- Sample ID format normalization (e.g., '20250710-2D' matches existing '20250710_2D')
- pXRF reading numbers not found in database (link still created with note)
- Duplicate ExternalAnalysis prevention (skipped silently)

**UI Display:**
- Errors: Shown as red error messages, upload rolls back
- Warnings: Shown in collapsible expander after successful upload

## Migration Notes

### Removing Foreign Key Constraint (2024-11-05)
**Migration:** `34cd6e250e16_remove_pxrf_fk.py`

**Reason:** Changed from single FK constraint to flexible String field to support:
- Multiple readings per sample (comma-separated)
- Forward compatibility (link samples before readings uploaded)
- String-based reading numbers (alphanumeric support)

**Before:**
```python
pxrf_reading_no = Column(String, ForeignKey("pxrf_readings.reading_no"))
```

**After:**
```python
pxrf_reading_no = Column(String, nullable=True, index=True)
```

**Impact:** More flexible but requires application-level validation (handled by RockInventoryService)

## Related Files

### Models
- `database/models/analysis.py` - PXRFReading, ExternalAnalysis, AnalysisFiles
- `database/models/samples.py` - SampleInfo, SamplePhotos

### Services
- `backend/services/bulk_uploads/pxrf_data.py` - PXRFUploadService
- `backend/services/bulk_uploads/rock_inventory.py` - RockInventoryService

### UI Components
- `frontend/components/bulk_uploads.py` - handle_pxrf_upload(), handle_rock_samples_upload()

### Data Migrations
- `database/data_migrations/normalize_pxrf_reading_numbers_008.py` - Fixes historical data format inconsistencies

### Database Migrations
- `database/migrations/versions/34cd6e250e16_remove_pxrf_fk.py` - Removes FK constraint

