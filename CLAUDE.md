# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install for development
uv pip install --upgrade -e .

# Run tests
uv run pytest

# Run a single test file
uv run pytest tests/test_dbf.py -q

# Format code
uvx ruff format

# Lint code
uvx ruff check

# Install system-wide (run after every update)
uv tool install --reinstall --from . lk_cli
```

## Development Rules

1. **TDD required** — write failing tests first (RED), then implement until they pass (GREEN) for all new code and changes.
2. **Install after every update** — always run `uv tool install --reinstall --from . lk_cli` after any change.
3. **Version bumps** — update `version` in `pyproject.toml` according to:
   - Change to an existing utility → increment the third number: `0.9.3.5` → `0.9.3.6`
   - New utility added → increment the second number, reset the third: `0.9.3.6` → `0.9.4.0`

## Architecture

**lk_cli** is a collection of CLI utilities for file hashing and comparison, using xxHash64 for speed and multiprocessing for performance.

### Entry Points

14 standalone CLI commands, each in its own module:

| Command | Module | Purpose |
|---------|--------|---------|
| `hw` | hw.py | Hash Write — generate JSON hash files for a folder (multiprocessing) |
| `mf` | mf.py | Missing Files — compare two folders, report missing files (multiprocessing) |
| `mf2` | mf2.py | Missing Files one-way — files in folder2 not in folder1 |
| `mfs` | mfs.py | Missing Files Sequential — sequential version of `mf` for validation |
| `ch` | ch.py | Check Hash — verify a folder's hash file is still current |
| `hc` | hc.py | Hash Compare — compare two folders using their hash files |
| `fhc` | fhc.py | Folder Hash Compare — compare folders by subfolder |
| `dedup` | dedup.py | Duplicate Detector — find and move duplicates to Desktop |
| `hp` | hp.py | Hash Print — print xxHash64 of specified files |
| `uc` | uc.py | URL Cleaner — strip tracking parameters from URLs |
| `dbf` | dbf.py | Database Files — build SQLite DB of image files with hash and EXIF data |
| `dbc` | dbc.py | Database Compare — find images in folder2's DB missing from folder1's DB |
| `dbi` | dbi.py | Database Image Inspector — interactively review missing images from a dbc results file |

`lk_cli.py` is a master help command that dynamically imports each module and displays its docstring.

### Shared Utilities (`utils.py`)

All core logic lives here:
- `hash_file()` / `hash_folder()` / `hash_folder_mp()` — file and folder hashing
- `read_hash()` / `read_hashes()` / `write_json()` — JSON hash file I/O
- `process_file()` — multiprocessing worker for file hashing
- `get_version()` — reads version from installed metadata or falls back to pyproject.toml
- `get_folders()` — lists subfolders, excluding hidden ones

Key constants: `os.cpu_count() or 8` multiprocessing cores, 1MB block size for reading.

### Design Patterns

- Each CLI module is a self-contained Click command with its own `--version` flag
- Hash files are stored as JSON alongside the hashed folder
- Multiprocessing variants (`mf`, `hw`) exist alongside sequential variants (`mfs`) for validation
- Broken symlinks and missing files are handled gracefully in `hash_file()`

## Dependencies

- **click** >=8.0 — CLI framework
- **xxhash** >=3.5.0 — fast non-cryptographic hashing
- **uv** — package manager (preferred over pip)
- **ruff** — formatter and linter
