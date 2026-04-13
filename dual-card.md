# Removal of Dual-Card Detection

## Background

Earlier versions of `dbc` included a dedicated "Dual-card copies" category. When a
camera writes simultaneously to two memory cards (e.g., Nikon dual-slot backup), the
resulting files share the same EXIF metadata (camera model, capture time, sub-second)
but carry different `memory_card_number` values. `dbc` detected this by reading
`memory_card_number` from both records and flagging EXIF matches where the numbers
differed.

## Why It Was Removed

The introduction of the **image-only hash** (Pass 2) made dual-card detection
redundant. A dual-card copy produces two files with byte-for-byte identical pixel
data but differing metadata. The image hash — computed from decoded pixel content
only, ignoring all metadata — catches this case exactly and more broadly: it also
handles format conversions, metadata strips, and any other operation that preserves
pixels while changing the file wrapper.

Because image-hash matching (Pass 2) runs before EXIF matching (Pass 3), a genuine
dual-card copy now resolves in Pass 2 as an "Image hash match" and never reaches the
EXIF pass. The `is_dual_card` flag on the EXIF tuple was therefore always `False` for
real dual-card copies, making it both misleading and unused.

## Changes Made (version 0.9.6.0 → 0.9.6.1)

### `lk_cli/dbc.py`

- **`compare_records`**
  - Removed `is_dual` boolean computation (was checking differing `memory_card_number`
    values on both EXIF-matched records).
  - `db1_exif` dict now maps the EXIF key to `row.name` (string) rather than
    `(row.name, row.memory_card_number)` (2-tuple).
  - `exif_only` entries are now 2-tuples `(db2_name, db1_name)` instead of 3-tuples.
  - Updated docstring to remove `is_dual_card` description and the dual-card mention
    in the Pass 2 description.

- **`write_results`**
  - Removed the split of `exif_only` into `dual_card` + `reencoded` lists.
  - Removed the separate "Dual-card copies:" output section.
  - All EXIF matches are now written under the single label
    `"EXIF matches (re-encoded/edited):"`.

### `lk_cli/dbm.py`

- Removed `"Dual-card copies:"` from `MOVEABLE_SECTIONS`.
- Updated `parse_matched_files` docstring (removed "Dual-card" from the section list).
- Updated `dbm` command docstring: "four high-confidence match types" → "three".

### `tests/test_dbc.py`

- Deleted entire `TestDualCard` class (5 tests):
  - `test_exif_only_tuple_has_three_elements`
  - `test_different_card_numbers_sets_is_dual_true`
  - `test_same_card_number_sets_is_dual_false`
  - `test_missing_card_number_sets_is_dual_false`
  - `test_dual_card_annotation_in_results_file` (×2 — was duplicated)
  - `test_non_dual_exif_match_not_annotated`
- Replaced `TestExifSectionLabels` with a slimmed-down version:
  - Removed `test_dual_card_entries_use_dual_card_header`
  - Removed `test_mixed_exif_shows_both_sections`
  - Removed `test_dual_card_in_results_file`
  - Kept `test_exif_entries_use_reencoded_header` (updated to use 2-tuple)
  - Kept `test_reencoded_in_results_file`
- Fixed `TestCompareRecords.test_exif_match_records_db1_name`: changed
  `exif_only[0][:2]` to `exif_only[0]` now that tuples are 2-elements.

### `tests/test_dbm.py`

- Removed `dual_card` parameter from `make_results_file` helper (signature and body).
- Deleted `test_dual_card_parsed`.
- Renamed `test_all_four_sections_combined` → `test_all_three_sections_combined`;
  updated fixture (removed `dual_card=`) and count assertion (`4` → `3`).
- Deleted `test_moves_dual_card_to_duplicates`.

### `pyproject.toml`

- Version bumped `0.9.6.0` → `0.9.6.1` (change to existing utility).
