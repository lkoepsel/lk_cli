# Optimization 3 & 4: Shared pool across calls + dynamic core count

## Problem

**Issue #3:** `hash_folder_mp` creates and destroys a `Pool` on every call. `mf.py` calls
it twice in sequence; `hw.py` calls it once per folder in a loop. Each call forks 8
processes and tears them down — significant overhead that can be amortized by sharing one
pool across calls.

**Issue #4:** `CORES = 8` is hardcoded. On machines with fewer cores it over-subscribes;
on machines with more it leaves capacity unused.

---

## Files Changed

| File | Change |
|------|--------|
| `lk_cli/utils.py` | `CORES = os.cpu_count() or 8`; add `pool=None` param to `hash_folder_mp`; add `get_pool()` helper |
| `lk_cli/mf.py` | Create one pool with `get_pool()`, pass to both `hash_folder_mp` calls |
| `lk_cli/hw.py` | Create one pool with `get_pool()`, pass to each `hash_folder_mp` call in the loop |
| `tests/test_utils.py` | New `TestSharedPool` and `TestCores` classes |

---

## Code Changes

### `utils.py` — issue #4: dynamic core count

```python
# BEFORE
CORES = 8

# AFTER
CORES = os.cpu_count() or 8
```

### `utils.py` — issue #3: optional pool parameter + helper

```python
# NEW helper
def get_pool():
    """Return a Pool sized to CORES for use as a context manager."""
    return Pool(CORES)


# CHANGED signature
def hash_folder_mp(folder_path, pool=None):
    all_filepaths = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if not dot_file.match(file):
                all_filepaths.append(os.path.join(root, file))

    hashes = {}
    if all_filepaths:
        if pool is not None:
            results = pool.map(partial(process_file, folder_path), all_filepaths)
        else:
            with Pool(CORES) as p:
                results = p.map(partial(process_file, folder_path), all_filepaths)
        for result in results:
            if result:
                file_hash, relpath = result
                hashes[file_hash] = relpath

    return hashes, hash_hashes(hashes)
```

### `mf.py` — share one pool for both folder hashes

```python
# BEFORE
from lk_cli.utils import hash_folder_mp, get_version

folder1_hashes = hash_folder_mp(folder1)
folder2_hashes = hash_folder_mp(folder2)

# AFTER
from lk_cli.utils import hash_folder_mp, get_version, get_pool

with get_pool() as pool:
    folder1_hashes = hash_folder_mp(folder1, pool=pool)
    folder2_hashes = hash_folder_mp(folder2, pool=pool)
```

### `hw.py` — share one pool across all folders in the loop

```python
# BEFORE
from lk_cli.utils import last_modified_file, hash_folder_mp, write_json, get_version

with click.progressbar(folders) as progressbar:
    for folder in progressbar:
        folder_hashes, folder_hash = hash_folder_mp(folder)

# AFTER
from lk_cli.utils import last_modified_file, hash_folder_mp, write_json, get_version, get_pool

with get_pool() as pool:
    with click.progressbar(folders) as progressbar:
        for folder in progressbar:
            folder_hashes, folder_hash = hash_folder_mp(folder, pool=pool)
```

---

## Red/Green TDD Plan

### Step 1: Write failing tests (RED)

Four tests are written to fail against the current code:

1. **`test_cores_uses_cpu_count`** — reloads the module with `os.cpu_count` mocked to
   return `42` and asserts `CORES == 42`. Fails now because `CORES = 8` is a literal.

2. **`test_get_pool_exists`** — imports `get_pool` from `utils`. Fails now with
   `ImportError` because `get_pool` does not exist.

3. **`test_hash_folder_mp_accepts_pool_param`** — calls `hash_folder_mp(folder, pool=p)`
   with an explicit pool. Fails now with `TypeError: unexpected keyword argument`.

4. **`test_pool_not_constructed_when_passed`** — passes a real pool into
   `hash_folder_mp`, patches `lk_cli.utils.Pool`, and asserts the constructor was not
   called. Fails now because `hash_folder_mp` ignores the pool argument (it doesn't
   exist yet) and always calls `Pool()` internally.

Regression tests (GREEN both before and after):
- `test_hash_folder_mp_default_still_works` — no pool arg, behavior unchanged
- `test_get_pool_is_context_manager` — returned object supports `with` statement
- `test_cores_fallback_when_cpu_count_none` — `os.cpu_count()` returning `None` gives 8

### Step 2: Run — watch them fail

```bash
uv run pytest -v tests/test_utils.py::TestCores tests/test_utils.py::TestSharedPool
```

### Step 3: Apply code changes (GREEN)

```bash
uv run pytest -v tests/test_utils.py   # all 25 existing + new tests pass
```

---

## Edge Cases Covered

| Case | Test |
|------|------|
| `os.cpu_count()` returns a number | `test_cores_uses_cpu_count` |
| `os.cpu_count()` returns `None` | `test_cores_fallback_when_cpu_count_none` |
| `get_pool` exists and is a context manager | `test_get_pool_is_context_manager` |
| Pool not re-created when one is passed in | `test_pool_not_constructed_when_passed` |
| `hash_folder_mp` still works with no pool arg | `test_hash_folder_mp_default_still_works` |
| Results correct when shared pool is used | `test_results_correct_with_shared_pool` |
