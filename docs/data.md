# Data Store

`SqliteData` provides a lightweight, thread-safe SQLite store for structured outputs.

## Connection
- Default path: `.gryt.db` in the working directory.
- In-memory mode: `SqliteData(in_memory=True)` for fast, ephemeral runs.

## Common Table: steps_output
- Created on demand by `CommandStep`:
  - `id TEXT PRIMARY KEY`
  - `result TEXT` (JSON of the step's returned dict)
  - `timestamp DATETIME DEFAULT CURRENT_TIMESTAMP`

## Tips
- Primary key conflicts: If you re-run a pipeline with the same step ids into the same DB file, an INSERT may fail due to the primary key constraint. Options:
  - Use unique ids per run (e.g., add suffix with timestamp/UUID).
  - Delete/rotate `.gryt.db` between runs.
  - Use `in_memory=True` while iterating locally.
- For your own tables, call `data.create_table(name, schema)` and then `data.insert(name, data_dict)`.
- `data.query(sql, params)` returns a list of dicts with auto JSON parsing.
- `data.update(table, data_dict, where, params)` can modify rows.

## Example
```python
from gryt import SqliteData

data = SqliteData(in_memory=True)
data.create_table('artifacts', {
  'id': 'TEXT PRIMARY KEY',
  'meta': 'TEXT',
})

data.insert('artifacts', {'id': 'build-1', 'meta': {'commit': 'abc123', 'status': 'ok'}})
rows = data.query('SELECT * FROM artifacts WHERE id = ?', ('build-1',))
print(rows)
```
