# Optimization 5, 6 & 7: Eliminate redundant walk, parallel dedup, fix hc bug

## Problems

**Issue #5 (`hw.py`):** `hash_folder_mp` already walks the entire tree to collect
filepaths. `hw` then calls `last_modified_file` which walks it a second time just to find
the max mtime. Since mtime is available during the first walk, it can be tracked there
and returned, eliminating the second traversal entirely.

**Issue #6 (`dedup.py`):** File hashing is sequential — `hash_file` is called in a plain
`for` loop with no multiprocessing. For large folders this is the bottleneck.

**Issue #7 (`hc.py`):** Line 38 uses `hash` (the Python builtin function) as a dict key
instead of `filehash` (the loop variable). This always raises `KeyError`, silently caught
by the `except` block, so the no-match detection branch is dead code.

---

## Files Changed

| File | Change |
|------|--------|
| `lk_cli/utils.py` | `hash_folder_mp` returns 3-tuple; add `hash_files_for_dedup`; add `defaultdict` import |
| `lk_cli/hw.py` | Unpack 3rd return value; remove `last_modified_file` import and call |
| `lk_cli/dedup.py` | Replace sequential walk+hash loop with `hash_files_for_dedup` |
| `lk_cli/hc.py` | `hashes1[hash]` → `hashes1[filehash]`; same fix in the echo string |
| `tests/test_utils.py` | Update 2-tuple unpacking to `*_`; add 3 new test classes |

---

## Code Changes

### Issue #5 — `utils.py`: track mtime during collection, return as 3rd element

```python
# BEFORE
def hash_folder_mp(folder_path, pool=None):
    all_filepaths = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if not dot_file.match(file):
                all_filepaths.append(os.path.join(root, file))
    ...
    return hashes, hash_hashes(hashes)

# AFTER
def hash_folder_mp(folder_path, pool=None):
    all_filepaths = []
    last_mtime = 0
    last_mpath = None
    for root, _, files in os.walk(folder_path):
        for file in files:
            filepath = os.path.join(root, file)
            try:
                mtime = os.path.getmtime(filepath)
                if mtime > last_mtime:
                    last_mtime = mtime
                    last_mpath = filepath
            except OSError:
                pass
            if not dot_file.match(file):
                all_filepaths.append(filepath)
    ...
    return hashes, hash_hashes(hashes), [last_mtime, last_mpath]
```

### Issue #5 — `hw.py`: unpack 3rd value, drop `last_modified_file`

```python
# BEFORE
from lk_cli.utils import last_modified_file, hash_folder_mp, write_json, get_version, get_pool
...
folder_hashes, folder_hash = hash_folder_mp(folder, pool=pool)
...
last_file = last_modified_file(folder)
hash["last_modified_file"] = last_file[1]
hash["last_modified_file_date"] = last_file[0]

# AFTER
from lk_cli.utils import hash_folder_mp, write_json, get_version, get_pool
...
folder_hashes, folder_hash, last_file = hash_folder_mp(folder, pool=pool)
...
hash["last_modified_file"] = last_file[1]
hash["last_modified_file_date"] = last_file[0]
```

### Issue #6 — `utils.py`: new `hash_files_for_dedup` function

```python
from collections import defaultdict   # add to imports

def hash_files_for_dedup(folder_path):
    """Hash all non-dot files in folder in parallel; return hash → [filepath, ...] map."""
    all_filepaths = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if not file.startswith("."):
                all_filepaths.append(os.path.join(root, file))

    hash_to_files = defaultdict(list)
    if all_filepaths:
        with get_pool() as pool:
            results = pool.map(hash_file, all_filepaths)
        for filepath, file_hash in zip(all_filepaths, results):
            if file_hash is not None:
                hash_to_files[file_hash].append(filepath)

    return hash_to_files
```

### Issue #6 — `dedup.py`: replace sequential loop

```python
# BEFORE
from lk_cli.utils import hash_file, get_version
...
hash_to_files = defaultdict(list)
for root, _, files in os.walk(folder):
    for file in files:
        if not file.startswith("."):
            filepath = os.path.join(root, file)
            try:
                file_hash = hash_file(filepath)
                hash_to_files[file_hash].append(filepath)
            except OSError as e:
                click.echo(click.style(f"Error reading {filepath}: {e}", fg="red"))
                continue

# AFTER
from lk_cli.utils import get_version, hash_files_for_dedup
...
hash_to_files = hash_files_for_dedup(folder)
```

Also remove the now-unused `from collections import defaultdict` import in `dedup.py`.

### Issue #7 — `hc.py`: fix `hash` builtin used as key

```python
# BEFORE (lines 38-39)
if hashes1[hash] != filename:
    click.secho(f"{hash} does not match", fg="red")

# AFTER
if hashes1[filehash] != filename:
    click.secho(f"{filehash} does not match", fg="red")
```

---

## Red/Green TDD Plan

### Step 1: Write failing tests (RED)

**Issue #5** — 2 RED tests:
- `test_return_type`: update assertion from `len == 2` to `len == 3` (fails now)
- `test_last_modified_identifies_newest`: use `os.utime` to set known mtimes; assert
  3rd element matches the newest file (fails now — only 2 values returned)

All other existing tests that unpack `hash_folder_mp` are updated to use `*_` extended
unpacking — they remain GREEN with both 2- and 3-tuple returns.

**Issue #6** — 4 RED tests (all fail with `ImportError` until `hash_files_for_dedup`
is added):
- `test_hash_files_for_dedup_groups_duplicates`
- `test_hash_files_for_dedup_excludes_dotfiles`
- `test_hash_files_for_dedup_uses_pool`
- `test_hash_files_for_dedup_returns_empty_for_empty_dir`

**Issue #7** — 2 RED tests (use `click.testing.CliRunner`):
- `test_hc_detects_path_mismatch`: same content at different paths in each folder;
  "does not match" must appear in output (currently the `except KeyError` masks it)
- `test_hc_no_keyerror_when_files_match`: same content at same path; output must NOT
  contain "KeyError" (currently the bug triggers KeyError for every match)

### Step 2: Run — watch them fail

```bash
uv run pytest -v tests/test_utils.py
```

### Step 3: Apply all code changes (GREEN)

```bash
uv run pytest -v tests/test_utils.py   # all 33 existing + new tests pass
```

---

## Edge Cases Covered

| Case | Test |
|------|------|
| Newest file correctly identified by mtime | `test_last_modified_identifies_newest` |
| 3rd tuple element present | `test_return_type` (updated to `len == 3`) |
| `hash_files_for_dedup` groups identical content | `test_hash_files_for_dedup_groups_duplicates` |
| Dotfiles excluded from dedup hashing | `test_hash_files_for_dedup_excludes_dotfiles` |
| Dedup hashing uses pool (not sequential) | `test_hash_files_for_dedup_uses_pool` |
| Empty folder returns empty dict | `test_hash_files_for_dedup_returns_empty_for_empty_dir` |
| `hc` detects same content at different paths | `test_hc_detects_path_mismatch` |
| `hc` does not crash with KeyError on matching files | `test_hc_no_keyerror_when_files_match` |
