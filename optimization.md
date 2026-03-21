# Performance Audit: `lk_cli/`

## 1. `utils.py` — `hash_folder_mp`: Pool dispatched per directory (HIGH IMPACT) **RESOLVED via optimization_1.md**

**Location:** `utils.py:94-95`

```python
for root, _, files in os.walk(folder_path):
    results = pool.map(partial(process_file, root, folder_path), files)
```

`pool.map` is called once *per subdirectory*, not once for all files. If a tree has 200 directories with 5 files each, that's 200 separate `pool.map` round-trips — each with IPC overhead and small batch sizes that leave workers idle. The fix is to collect all `(root, file)` pairs in a list first, then dispatch a single `pool.map` call, giving the scheduler a full workload to distribute optimally.

---

## 2. `utils.py` — `calculate_file_hash` uses 8 KB chunks vs 1 MB (MEDIUM IMPACT)

**Location:** `utils.py:15-21` vs `utils.py:12,68-70`

`calculate_file_hash` (used by `hp`) reads in 8 KB chunks. `hash_file` (used by everything else) reads in 1 MB chunks (`BLOCKSIZE`). For a 100 MB file, that's 12,800 read syscalls vs 100. The two functions are doing the same thing and should share the same block size.

---

## 3. `utils.py` — `Pool` created and destroyed per `hash_folder_mp` call (MEDIUM IMPACT)

**Location:** `utils.py:93`

In `mf.py`, `hash_folder_mp` is called twice in sequence — each call spawns 8 new processes and tears them down. In `hw.py`, it's called once per folder in a loop, same issue. Spawning a `Pool` is expensive (fork + import overhead per worker). A single pool passed in as a parameter, or a module-level pool, would amortize this cost.

---

## 4. `utils.py` — `CORES = 8` hardcoded (LOW IMPACT)

**Location:** `utils.py:11`

On machines with fewer than 8 cores this over-subscribes; on machines with more it leaves capacity unused. `os.cpu_count()` would be more appropriate.

---

## 5. `hw.py` — `last_modified_file` does a redundant full `os.walk` (LOW IMPACT)

**Location:** `hw.py:25`, `utils.py:112-125`

`hw` calls `hash_folder_mp` (which walks the entire tree) and then immediately calls `last_modified_file` (which walks it again just to find the max mtime). The mtime of each file is available during the hashing walk — tracking `max(mtime)` there would eliminate the second traversal.

---

## 6. `dedup.py` — file hashing is fully sequential (LOW-MEDIUM IMPACT)

**Location:** `dedup.py:30-34`

`hash_file` is called in a plain `for` loop. For large folders this is the bottleneck — it has no multiprocessing equivalent of `hash_folder_mp`. Adding a parallel hashing path here would bring it in line with the other tools.

---

## 7. `hc.py` — correctness bug (not performance, but worth flagging)

**Location:** `hc.py:38`

```python
if hashes1[hash] != filename:   # `hash` is the Python builtin, not `filehash`
```

`filehash` is the loop variable; `hash` is the built-in function. This lookup will always raise a `KeyError`, which is silently swallowed by the `except KeyError` block, so the no-match branch never executes. The comparison logic inside the loop is currently dead code.

---

## Summary by priority

| Priority | Issue | Location |
|----------|-------|----------|
| HIGH | `pool.map` called per directory instead of once for all files | `utils.py:94` |
| MEDIUM | `calculate_file_hash` uses 8 KB chunks; `hash_file` uses 1 MB | `utils.py:15,68` |
| MEDIUM | Pool created/destroyed on each `hash_folder_mp` call | `utils.py:93` |
| LOW | `CORES = 8` hardcoded | `utils.py:11` |
| LOW | `last_modified_file` re-walks tree already walked during hashing | `hw.py:25` |
| LOW-MED | `dedup` has no multiprocessing path | `dedup.py:30` |
| BUG | `hc.py` uses `hash` builtin instead of `filehash` loop var | `hc.py:38` |

The single biggest win would be restructuring `hash_folder_mp` to collect all files before dispatching — this affects `mf`, `hw`, and anything else calling that function.
