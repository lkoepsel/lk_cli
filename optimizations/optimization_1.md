# Optimization 1: Refactor `hash_folder_mp` — Single Pool Dispatch

## Problem

`hash_folder_mp` calls `pool.map` once *per subdirectory* during `os.walk`. For a tree
with N directories, that is N IPC round-trips with small batches that leave workers idle.

## Files Changed

- `lk_cli/utils.py` — only file with code changes
- `pyproject.toml` — add pytest config
- `tests/__init__.py` — new (empty)
- `tests/test_utils.py` — new test suite

`mf.py` and `hw.py` are unaffected; the public interface is unchanged.

---

## Code Changes

### `process_file` — new 2-arg signature

`root` is dropped. Caller passes the full `filepath`. Dotfile filtering moves to the
collection phase in `hash_folder_mp`.

```python
# BEFORE
def process_file(root, folder_path, file):
    if not dot_file.match(file):
        filepath = os.path.join(root, file)
        ...

# AFTER
def process_file(folder_path, filepath):
    if not os.path.exists(filepath):
        if os.path.islink(filepath):
            print(f"Warning: Skipping broken symlink '{filepath}'")
        else:
            print(f"Warning: Skipping missing file '{filepath}'")
        return None
    relpath = os.path.relpath(filepath, folder_path)
    file_hash = hash_file(filepath)
    if file_hash is not None:
        return file_hash, relpath
    return None
```

### `hash_folder_mp` — collect all files first, single dispatch

```python
# BEFORE
def hash_folder_mp(folder_path):
    hashes = {}
    with Pool(CORES) as pool:
        for root, _, files in os.walk(folder_path):
            results = pool.map(partial(process_file, root, folder_path), files)
            for result in results:
                if result:
                    file_hash, relpath = result
                    hashes[file_hash] = relpath
    return hashes, hash_hashes(hashes)

# AFTER
def hash_folder_mp(folder_path):
    all_filepaths = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if not dot_file.match(file):
                all_filepaths.append(os.path.join(root, file))

    hashes = {}
    if all_filepaths:
        with Pool(CORES) as pool:
            results = pool.map(partial(process_file, folder_path), all_filepaths)
        for result in results:
            if result:
                file_hash, relpath = result
                hashes[file_hash] = relpath

    return hashes, hash_hashes(hashes)
```

---

## Red/Green TDD Plan

### Step 0: Setup

Add to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

Create `tests/__init__.py` (empty) and `tests/test_utils.py`.

### Step 1: Write failing tests (RED)

Tests written against the post-refactor API. They fail against current code because:
- `process_file` still expects 3 args, not 2
- `pool.map` is still called once per directory

### Step 2: Run — watch them fail

```bash
uv pip install pytest
pytest -v tests/test_utils.py
```

### Step 3: Apply code changes (GREEN)

```bash
pytest -v tests/test_utils.py   # all pass
```

---

## Edge Cases Covered by Tests

| Case | Test |
|------|------|
| Empty directory — no pool spawned | `test_no_pool_spawned_for_empty_dir` |
| Dotfiles excluded | `test_dotfiles_excluded` |
| Broken symlink skipped, real files hashed | `test_broken_symlink_skipped_real_file_included` |
| Hash collision — one dict entry (documented) | `test_hash_collision_one_entry` |
| Nested subdir relative path correct | `test_relpath_for_nested_file` |
| Return type unchanged (mf/hw unaffected) | `test_return_type` |
| `pool.map` called exactly once regardless of depth | `test_pool_map_called_exactly_once` |
