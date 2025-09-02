# Data Store

`SqliteData` provides a lightweight, thread-safe SQLite store for structured outputs.

## Connection
- Default path: `.gryt/gryt.db` when using the CLI project structure (or a path you provide). The class default remains `.gryt.db` if not specified.
- In-memory mode: `SqliteData(in_memory=True)` for fast, ephemeral runs.

## Predefined Tables (auto-created)
On initialization/connection, `SqliteData` auto-creates the following tables (using `CREATE TABLE IF NOT EXISTS`):

- pipelines
  - `pipeline_id TEXT PRIMARY KEY`
  - `name TEXT`
  - `start_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP`
  - `end_timestamp DATETIME`
  - `status TEXT`
  - `config_json TEXT`

- runners
  - `runner_id TEXT PRIMARY KEY`
  - `pipeline_id TEXT` (FK -> pipelines.pipeline_id)
  - `name TEXT`
  - `execution_order INTEGER`
  - `status TEXT`

- steps_output
  - `step_id TEXT PRIMARY KEY`
  - `runner_id TEXT` (FK -> runners.runner_id)
  - `name TEXT`
  - `output_json TEXT` (JSON of the step's structured result)
  - `status TEXT`
  - `duration REAL`
  - `timestamp DATETIME DEFAULT CURRENT_TIMESTAMP`

- versions
  - `version_id TEXT PRIMARY KEY`
  - `app_name TEXT`
  - `version_string TEXT`
  - `commit_hash TEXT`
  - `timestamp DATETIME DEFAULT CURRENT_TIMESTAMP`

Notes:
- Foreign keys are enabled (`PRAGMA foreign_keys = ON`).
- The CLI `gryt init` creates `.gryt/gryt.db` and uses `SqliteData` to pre-populate the schema.

## Custom Tables
For your own data, call `data.create_table(name, schema)` and then `data.insert(name, data_dict)`. The schema dict maps column names to SQL types/constraints. Dict/list values are JSON-serialized automatically when inserting; queries auto-deserialize JSON-like strings.

## Tips
- Primary key conflicts: `steps_output.step_id` is a primary key. Use unique step ids per run (or rotate the DB) to avoid conflicts in persistent databases.
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
