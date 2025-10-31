# Cloud API Fix: Handle Generation Changes

## Problem

The API endpoints for creating and updating generations are not processing the `changes` array in the request payload. They need to save changes to the `generation_changes` table.

## Solution

### 1. POST /api/v1/generations (Create)

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid

router = APIRouter()

class ChangeCreate(BaseModel):
    id: str
    type: str
    title: str
    description: Optional[str] = None

class GenerationCreate(BaseModel):
    version: str
    description: Optional[str] = None
    changes: List[ChangeCreate] = []
    pipeline_template: Optional[str] = None
    status: str = "draft"

@router.post("/api/v1/generations")
def create_generation(
    generation_data: GenerationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a new generation with changes."""

    # Check if version already exists
    existing = db.execute(
        "SELECT id FROM generations WHERE version = ?",
        (generation_data.version,)
    ).fetchone()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Generation {generation_data.version} already exists"
        )

    # Generate IDs
    generation_id = str(uuid.uuid4())
    db_generation_id = None  # Auto-increment ID from database

    # Insert generation
    result = db.execute("""
        INSERT INTO generations (
            generation_id, version, description, status,
            pipeline_template, created_at, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        generation_id,
        generation_data.version,
        generation_data.description,
        generation_data.status,
        generation_data.pipeline_template,
        datetime.now(),
        current_user.username
    ))

    db_generation_id = result.lastrowid
    db.commit()

    # *** CRITICAL: Insert changes ***
    changes_count = 0
    for change in generation_data.changes:
        db.execute("""
            INSERT INTO generation_changes (
                change_id, generation_id, type, title,
                description, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            change.id,
            generation_id,  # Link to generation via generation_id (UUID)
            change.type,
            change.title,
            change.description,
            "pending",  # Default status
            datetime.now()
        ))
        changes_count += 1

    db.commit()

    # Return response with nested structure
    return {
        "status": 200,
        "message": "Generation created",
        "data": {
            "id": db_generation_id,  # Auto-increment ID
            "generation_id": generation_id,  # UUID
            "version": generation_data.version,
            "description": generation_data.description,
            "changes_count": changes_count
        }
    }
```

### 2. PATCH /api/v1/generations/{generation_id} (Update)

```python
class GenerationUpdate(BaseModel):
    version: Optional[str] = None
    description: Optional[str] = None
    changes: Optional[List[ChangeCreate]] = None
    pipeline_template: Optional[str] = None
    status: Optional[str] = None

@router.patch("/api/v1/generations/{generation_id}")
def update_generation(
    generation_id: int,  # Auto-increment ID
    generation_data: GenerationUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update a generation and its changes."""

    # Get existing generation
    existing = db.execute(
        "SELECT generation_id, version FROM generations WHERE id = ?",
        (generation_id,)
    ).fetchone()

    if not existing:
        raise HTTPException(status_code=404, detail="Generation not found")

    generation_uuid = existing["generation_id"]

    # Update generation metadata
    update_fields = []
    update_values = []

    if generation_data.version is not None:
        update_fields.append("version = ?")
        update_values.append(generation_data.version)

    if generation_data.description is not None:
        update_fields.append("description = ?")
        update_values.append(generation_data.description)

    if generation_data.pipeline_template is not None:
        update_fields.append("pipeline_template = ?")
        update_values.append(generation_data.pipeline_template)

    if generation_data.status is not None:
        update_fields.append("status = ?")
        update_values.append(generation_data.status)

    if update_fields:
        update_values.append(generation_id)
        db.execute(
            f"UPDATE generations SET {', '.join(update_fields)} WHERE id = ?",
            tuple(update_values)
        )
        db.commit()

    # *** CRITICAL: Handle changes array ***
    if generation_data.changes is not None:
        # Strategy 1: Replace all changes (recommended for simplicity)
        # Delete existing changes
        db.execute(
            "DELETE FROM generation_changes WHERE generation_id = ?",
            (generation_uuid,)
        )

        # Insert new changes
        changes_count = 0
        for change in generation_data.changes:
            db.execute("""
                INSERT INTO generation_changes (
                    change_id, generation_id, type, title,
                    description, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                change.id,
                generation_uuid,  # Link to generation via UUID
                change.type,
                change.title,
                change.description,
                "pending",
                datetime.now()
            ))
            changes_count += 1

        db.commit()

    # Return updated generation
    return {
        "status": 200,
        "message": "Generation updated",
        "data": {
            "id": generation_id,
            "generation_id": generation_uuid,
            "version": generation_data.version or existing["version"],
            "changes_count": changes_count if generation_data.changes else None
        }
    }
```

### 3. GET /api/v1/generations (List) - Include Changes

```python
@router.get("/api/v1/generations")
def list_generations(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """List all generations with changes."""

    # Get all generations for current user
    generations = db.execute("""
        SELECT
            id, generation_id, version, description,
            status, pipeline_template, created_at,
            promoted_at, created_by, promoted_by
        FROM generations
        WHERE created_by = ?
        ORDER BY created_at DESC
    """, (current_user.username,)).fetchall()

    result = []
    for gen in generations:
        # *** CRITICAL: Fetch changes for each generation ***
        changes = db.execute("""
            SELECT change_id, type, title, description, status
            FROM generation_changes
            WHERE generation_id = ?
            ORDER BY created_at
        """, (gen["generation_id"],)).fetchall()

        result.append({
            "id": gen["id"],
            "generation_id": gen["generation_id"],
            "version": gen["version"],
            "description": gen["description"],
            "status": gen["status"],
            "pipeline_template": gen["pipeline_template"],
            "created_at": gen["created_at"],
            "promoted_at": gen["promoted_at"],
            "created_by": gen["created_by"],
            "promoted_by": gen["promoted_by"],
            "changes_count": len(changes),
            # Include full changes array
            "changes": [
                {
                    "id": c["change_id"],
                    "type": c["type"],
                    "title": c["title"],
                    "description": c["description"],
                    "status": c["status"]
                }
                for c in changes
            ]
        })

    return {
        "status": 200,
        "message": "Generations listed",
        "data": {
            "generations": result
        }
    }
```

### 4. GET /api/v1/generations/{generation_id} (Get Single)

```python
@router.get("/api/v1/generations/{generation_id}")
def get_generation(
    generation_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get a single generation with all its changes."""

    # Get generation
    gen = db.execute("""
        SELECT
            id, generation_id, version, description,
            status, pipeline_template, created_at,
            promoted_at, created_by, promoted_by
        FROM generations
        WHERE id = ?
    """, (generation_id,)).fetchone()

    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found")

    # *** CRITICAL: Fetch changes ***
    changes = db.execute("""
        SELECT change_id, type, title, description, status
        FROM generation_changes
        WHERE generation_id = ?
        ORDER BY created_at
    """, (gen["generation_id"],)).fetchall()

    return {
        "status": 200,
        "message": "Generation retrieved",
        "data": {
            "id": gen["id"],
            "generation_id": gen["generation_id"],
            "version": gen["version"],
            "description": gen["description"],
            "status": gen["status"],
            "pipeline_template": gen["pipeline_template"],
            "created_at": gen["created_at"],
            "promoted_at": gen["promoted_at"],
            "created_by": gen["created_by"],
            "promoted_by": gen["promoted_by"],
            "changes": [
                {
                    "id": c["change_id"],
                    "type": c["type"],
                    "title": c["title"],
                    "description": c["description"],
                    "status": c["status"]
                }
                for c in changes
            ]
        }
    }
```

## Key Points

1. **Always process the `changes` array** in POST and PATCH requests
2. **Always include the `changes` array** in GET responses
3. **Use `generation_id` (UUID)** as the foreign key, not the auto-increment `id`
4. **Delete and replace** strategy for updates is simplest (alternative: merge/upsert)
5. **Return nested structure** with `{"status": 200, "data": {...}}`

## Testing

After implementing these changes, test with:

```bash
cd ~/code/stllr
gryt generation new v2.4.0
# Edit YAML with changes
gryt generation update v2.4.0
gryt sync push

# Fresh database pull
rm .gryt/gryt.db
gryt init
gryt sync pull
sqlite3 .gryt/gryt.db "SELECT * FROM generation_changes;"
# Should show all changes!
```
