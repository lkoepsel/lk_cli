# Optimization 2: Unify chunk size in `calculate_file_hash`

## Problem

`calculate_file_hash` (used by `hp`) defaults to 8 KB chunks. `hash_file` (used by
everything else) uses `BLOCKSIZE = 1048576` (1 MB). For a 100 MB file that is 12,800
`read()` syscalls vs 100. The two functions do the same thing and should use the same
block size.

## Files Changed

- `lk_cli/utils.py` — one-character fix: `chunk_size=8192` → `chunk_size=BLOCKSIZE`
- `tests/test_utils.py` — new `TestCalculateFileHash` class appended

`hp.py` is unaffected; it calls `calculate_file_hash(file_path)` with no `chunk_size`
argument, so it benefits automatically from the corrected default.

---

## Code Change

```python
# BEFORE
def calculate_file_hash(file_path, chunk_size=8192):

# AFTER
def calculate_file_hash(file_path, chunk_size=BLOCKSIZE):
```

---

## Red/Green TDD Plan

### Step 1: Write failing tests (RED)

Two tests are written to fail against the current code:

1. **`test_default_chunk_size_equals_blocksize`** — inspects the function signature and
   asserts the default equals `BLOCKSIZE`. Fails now because default is `8192`.

2. **`test_large_file_read_count`** — creates a file slightly larger than 2 × BLOCKSIZE,
   wraps the file handle's `read` method to count calls, and asserts exactly 3 reads
   occur (2 full blocks + 1 remainder). Fails now because 8 KB chunks produce many more
   reads.

Additional regression tests pass both before and after (correctness, not performance):

- `test_produces_correct_hash` — result matches a directly computed xxhash64
- `test_matches_hash_file` — `calculate_file_hash` and `hash_file` return the same value
- `test_small_file_hash` — file smaller than both chunk sizes
- `test_empty_file_hash` — empty file edge case

### Step 2: Run — watch them fail

```bash
uv run pytest -v tests/test_utils.py::TestCalculateFileHash
```

### Step 3: Apply the one-line fix (GREEN)

```bash
uv run pytest -v tests/test_utils.py   # all 19 existing + new tests pass
```

---

## Edge Cases Covered

| Case | Test |
|------|------|
| Default chunk size equals BLOCKSIZE | `test_default_chunk_size_equals_blocksize` |
| Read syscall count for large file | `test_large_file_read_count` |
| Hash correctness vs xxhash reference | `test_produces_correct_hash` |
| Consistency with `hash_file` | `test_matches_hash_file` |
| File smaller than chunk size | `test_small_file_hash` |
| Empty file | `test_empty_file_hash` |
