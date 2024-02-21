## 2.0.0 (2024-02-21)

### BREAKING CHANGE

- `query_class` *must* now be defined on a repository subclass.

### Feat

- Handle nested models more gracefully; add per-field data prep
- Local filesystem-based filestorage implementation
- Teach queries insert, update, delete, which repos now use
- add README.md, LICENSE.md, better package metadata

## 1.0.3 (2024-01-27)

### Fix

- AbstractSQLRepository().get() must send a dict to prepare_data_for_entity()

## 1.0.2 (2024-01-26)

### Fix

- AbstractShelveQuery().run_data_query() should return dicts, not PMaps

## 1.0.1 (2024-01-26)

### Fix

- AbstractInMemoryQuery().run_data_query() should return dicts, not PMaps

## 1.0.0 (2024-01-25)

### Feat

- Implement Repository pattern with pluggable storages
