# Experiment Description Property

## Overview

The `Experiment` model uses a property-based approach for descriptions. Instead of storing the description as a direct column, it leverages the `ExperimentNotes` relationship, where **the first note (by creation time) serves as the experiment's description**.

## Implementation

### Reading the Description

```python
from database.models import Experiment

# Get an experiment
experiment = session.query(Experiment).filter_by(experiment_id="HPHT_MH_001").first()

# Access the description (returns the first note's text)
description = experiment.description
# Returns: str or None
```

### Setting the Description

```python
# Create a new experiment
exp = Experiment(
    experiment_id="HPHT_MH_001",
    experiment_number=1,
    status='COMPLETED',
    date=datetime.now()
)
session.add(exp)
session.flush()  # Important: flush to get the ID

# Set the description (creates a new note)
exp.description = "High pressure, high temperature leach test"
session.commit()
```

### Updating the Description

```python
# Update the description (modifies the first note)
exp.description = "Updated description text"
session.commit()
```

## How It Works

### Property Getter

The `description` property getter:
1. Checks if the experiment has any notes
2. Returns the `note_text` of the first note (ordered by `created_at`)
3. Returns `None` if no notes exist

```python
@property
def description(self):
    if self.notes and len(self.notes) > 0:
        return self.notes[0].note_text
    return None
```

### Property Setter

The `description` property setter:
1. If notes exist: Updates the `note_text` of the first note
2. If no notes exist: Creates a new `ExperimentNotes` record
3. Does nothing if value is empty

```python
@description.setter
def description(self, value):
    if not value:
        return
    
    if self.notes and len(self.notes) > 0:
        # Update existing note
        self.notes[0].note_text = value
    else:
        # Create new note
        note = ExperimentNotes(
            experiment_id=self.experiment_id,
            experiment_fk=self.id,
            note_text=value,
            created_at=datetime.now()
        )
        self.notes.append(note)
```

## Important Notes

### Order of Notes

The `notes` relationship is ordered by `created_at` ascending, ensuring the first note is always the oldest:

```python
notes = relationship("ExperimentNotes", 
                    back_populates="experiment", 
                    cascade="all, delete-orphan", 
                    order_by="ExperimentNotes.created_at")
```

### Additional Notes

While the first note serves as the description, you can still add additional notes:

```python
# Add another note (not the description)
from database.models import ExperimentNotes

additional_note = ExperimentNotes(
    experiment_id=exp.experiment_id,
    experiment_fk=exp.id,
    note_text="Additional observation about the experiment"
)
session.add(additional_note)
session.commit()

# The description still returns the first note
print(exp.description)  # Still returns the original description
```

### Flushing Before Setting Description

When creating a new experiment, you must flush to get the `id` before setting the description:

```python
exp = Experiment(experiment_id="TEST_001", experiment_number=1, status='COMPLETED')
session.add(exp)
session.flush()  # ✓ Get the ID

exp.description = "My description"  # ✓ Works because exp.id is set
session.commit()
```

Without flushing:

```python
exp = Experiment(experiment_id="TEST_001", experiment_number=1, status='COMPLETED')
session.add(exp)
exp.description = "My description"  # ✗ May fail - exp.id is None
session.commit()
```

## Benefits

1. **Consistency**: Description is always stored with notes
2. **History**: All notes (including description) have timestamps
3. **Flexibility**: Can have multiple notes, with the first serving as the description
4. **No Schema Change**: Uses existing `ExperimentNotes` table

## Usage in Forms

When creating an experiment form, you can now use `description` directly:

```python
# Streamlit example
description = st.text_area("Experiment Description", value=experiment.description or "")

if st.button("Save"):
    experiment.description = description
    session.commit()
```

## Database Schema

No changes to the database schema are needed. The property uses the existing relationship:

```
experiments
  ├── id (PK)
  ├── experiment_id
  └── ...

experiment_notes
  ├── id (PK)
  ├── experiment_fk (FK → experiments.id)
  ├── note_text
  ├── created_at
  └── ...
```

## Migration from Direct Description Column

If you previously had a `description` column and want to migrate:

```python
# Hypothetical migration
def migrate_descriptions(session):
    experiments = session.query(Experiment).all()
    
    for exp in experiments:
        if hasattr(exp, '_description_column') and exp._description_column:
            # Create note from old description column
            note = ExperimentNotes(
                experiment_id=exp.experiment_id,
                experiment_fk=exp.id,
                note_text=exp._description_column
            )
            session.add(note)
    
    session.commit()
```

## Testing

See `tests/test_lineage_migration.py::test_description_property` for comprehensive tests of this functionality.

```bash
python -m pytest tests/test_lineage_migration.py::TestExperimentLineageMigration::test_description_property -v
```

