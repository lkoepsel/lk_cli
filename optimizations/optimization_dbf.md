# dbf / dbc Optimization: Extended Metadata, Perceptual Hashing, Progress Bar, and Output File

## Motivation

The original `dbf`/`dbc` pair compared images in two passes:

1. **Hash match** — byte-for-byte identical files (exact xxHash64 match)
2. **EXIF match** — same `camera_model` + `created_at` with a different hash

This worked well for straightforward cases but had two gaps:
- Burst shots taken in the same second by the same camera would EXIF-match each other (false positive)
- Re-encoded, format-converted (HEIC→JPG), or lightly edited images with different EXIF data or none at all were reported as missing

This update adds sub-second EXIF precision, richer metadata columns, and a third matching pass using **perceptual hashing (pHash)**.

---

## New File Characteristics

### Sub-second time (`subsec_time`)

**EXIF tag 37521** — `SubSecTimeOriginal`, stored in the Exif sub-IFD (0x8769).

Many cameras (Canon, Nikon, Sony, Apple) write a sub-second suffix alongside `DateTimeOriginal`. Without it, two burst frames from the same camera in the same second share an identical `(camera_model, created_at)` key and would incorrectly EXIF-match.

The EXIF key for Pass 2 is now `(camera_model, created_at, subsec_time)`. When both records have `subsec_time = None` (cameras that don't write it), the key is `(model, time, None)` and matching still works correctly.

**Impact:** Eliminates false-positive EXIF matches between burst shots.

### Image dimensions (`image_width`, `image_height`)

Read directly from PIL (`img.width`, `img.height`) — always available for any successfully opened image. Stored as `INTEGER` columns.

Useful for future queries (e.g., find all images above a certain resolution, identify format-converted copies that changed resolution).

### File size (`file_size`)

`os.path.getsize(filepath)` captured before opening the image. A fast metadata column requiring no decoding. Useful for filtering and future comparison strategies.

### Image unique ID (`image_unique_id`)

**EXIF tag 42016** (`ImageUniqueID`), Exif sub-IFD. A per-image UUID written by some cameras (Canon is a common example). If present, this is a definitive identity for a single capture, independent of filename or encoding.

### Camera serial (`camera_serial`)

**EXIF tag 42033** (`BodySerialNumber`), Exif sub-IFD (with IFD0 fallback). Distinguishes two identical camera models owned by different people — a useful complement to `camera_model` for edge cases.

---

## Perceptual Hashing (pHash)

### What it is

A perceptual hash encodes the *visual content* of an image as a compact fingerprint (64 bits). Unlike xxHash64, which changes completely for any byte difference, a pHash changes slowly — visually similar images have pHashes close together (small Hamming distance).

### How pHash works (DCT method)

1. **Resize** the image to 32×32 pixels
2. **Convert to grayscale** (removes color information, focuses on structure)
3. **Apply 2D DCT** (Discrete Cosine Transform) — the same transform used internally by JPEG
4. **Take the top-left 8×8 block** of DCT coefficients (the low-frequency components that carry most visual information)
5. **Threshold at the median** — each of the 64 coefficients is set to 1 if above the median, 0 if below
6. **Result:** a 64-bit hash stored as a 16-character hex string

The DCT step is why pHash is more robust than simpler alternatives: it operates in the frequency domain, making it resistant to the exact transforms JPEG encoding applies during re-compression.

### Comparison: Hamming distance

Two pHashes are compared by counting the number of bit positions that differ (Hamming distance):

```python
h1 = imagehash.hex_to_hash(phash1)
h2 = imagehash.hex_to_hash(phash2)
distance = h1 - h2  # integer, 0–64
```

| Distance | Interpretation |
|----------|---------------|
| 0 | Bit-for-bit identical visual content |
| 1–5 | Near-identical (minor re-encoding, slight crop) |
| 6–10 | Likely the same image (edited, format-converted) |
| 11–20 | Possibly related |
| >20 | Different images |

**Default threshold: 10.** This is the widely-accepted standard for photo library deduplication. It catches:
- HEIC→JPG format conversion
- Re-saved JPEGs at different quality settings
- Slight brightness/contrast adjustments
- Minor crops (small)

### Why pHash over alternatives

| Method | Basis | Speed | Accuracy | Robust to re-encoding |
|--------|-------|-------|----------|----------------------|
| **pHash** | DCT (frequency domain) | Fast | Best | Yes |
| dHash | Gradient (edge differences) | Fastest | Good | Mostly |
| aHash | Average pixel value | Fastest | Weakest | Partial |
| Pixel diff | Raw comparison | Slow | Exact | No |

pHash is preferred here because JPEG compression operates in the DCT domain — using the same mathematical basis makes pHash naturally resistant to JPEG re-encoding artifacts.

### Important limitation: solid-color images

For images with no internal structure (pure solid colors), the DCT yields only a single non-zero DC component. The median threshold lands at zero, and the resulting hash is the same for any non-black solid color. In practice this means solid-color test images will match each other by pHash even if they're different colors. Real photographs have rich texture and will produce distinct pHashes.

---

## Implementation Details

### New DB schema (`.dbf.db`)

```sql
CREATE TABLE files (
    hash             TEXT,      -- xxHash64 of raw file bytes
    name             TEXT,      -- absolute file path
    created_at       TEXT,      -- EXIF DateTimeOriginal (tag 36867)
    camera_model     TEXT,      -- EXIF Model (tag 272, IFD0)
    subsec_time      TEXT,      -- EXIF SubSecTimeOriginal (tag 37521)
    image_width      INTEGER,   -- pixel width (from PIL)
    image_height     INTEGER,   -- pixel height (from PIL)
    file_size        INTEGER,   -- bytes on disk
    image_unique_id  TEXT,      -- EXIF ImageUniqueID (tag 42016)
    camera_serial    TEXT,      -- EXIF BodySerialNumber (tag 42033)
    phash            TEXT       -- 16-char hex perceptual hash
)
```

`DROP TABLE IF EXISTS files` runs before each `dbf` build, so the schema is always current. Old `.dbf.db` files are incompatible — re-run `dbf` to rebuild.

### Three-pass comparison in `dbc`

```
Pass 1 — Hash match
    db1_hashes = set of all xxHash64 values in folder1
    if db2_record.hash in db1_hashes → MATCHED (exact copy, possibly renamed)

Pass 2 — EXIF match
    db1_exif = dict of (camera_model, created_at, subsec_time) → name
    if db2_record has camera_model AND created_at:
        if (model, time, subsec) in db1_exif → MATCHED (re-encoded/edited copy)
    Note: subsec_time=None on both sides still matches (cameras without subsec support)

Pass 3 — pHash match
    db1_phashes = list of (ImageHash, name) for all db1 records with a phash
    if db2_record has phash:
        find first db1 record where Hamming distance ≤ threshold (default 10)
        if found → MATCHED (visually similar copy)

Unmatched → MISSING
```

### Output

```
Missing from /path/folder1 (not found by hash, EXIF, or pHash):
  /path/folder2/photo.jpg
Total missing: 1

Matched by EXIF only (different hash, same camera+time):
  /path/folder2/edited.jpg

Matched by pHash only (visually similar, different hash+EXIF):
  /path/folder2/converted.heic→jpg.jpg  [distance: 3]

All files in /path/folder2 accounted for in /path/folder1 (42 by hash, 3 by EXIF, 1 by pHash).
```

---

---

## Progress Bar (`dbf`)

`dbf` now shows a real-time progress bar during image processing.

### Implementation

The key change is switching from `pool.map` (blocking, returns all results at once) to `pool.imap_unordered` (streaming, yields results as workers finish):

```python
# Before — no progress visibility
results = pool.map(process_image, all_filepaths)

# After — progress bar updates as each worker completes
with click.progressbar(
    pool.imap_unordered(process_image, all_filepaths),
    length=len(all_filepaths),
    label="Processing images",
    file=sys.stderr,
) as bar:
    results = list(bar)
```

The progress bar writes to **stderr** so that piping stdout (e.g., to capture skip messages) does not include bar characters. In non-interactive contexts (pipes, CI, tests), click automatically suppresses the bar.

`imap_unordered` returns results as soon as each worker finishes rather than waiting for all workers. This means:
- The bar reflects actual completion, not estimated completion
- Result order is non-deterministic (acceptable — DB insertion order doesn't matter)
- Faster-completing images (smaller files) update the bar sooner, making it feel responsive

The ETA shown by click is computed from elapsed time divided by fraction complete, giving an accurate estimate once a few percent of files have been processed.

---

## Results File (`dbc`)

`dbc` now writes a structured results file after every run, defaulting to `~/Desktop/dbc_results.txt`.

### Usage

```bash
dbc folder1 folder2                          # writes to ~/Desktop/dbc_results.txt
dbc folder1 folder2 --output ~/reports/x.txt  # custom path
```

### Output file format

```
dbc Results
Generated:           2026-03-22 14:30:00
Folder1 (reference): /Volumes/Archive/Photos
Folder2 (checked):   /Volumes/Camera/Photos

Summary
--------------------------------------------------
  Hash matches:      42  (exact byte-for-byte copies)
  EXIF matches:       3  (same camera+time, different hash)
  pHash matches:      1  (visually similar, Hamming distance ≤ 5)
  Missing:            5  (not found by any method)
  Total in folder2:  51

Missing (not found by hash, EXIF, or pHash): 5
  /Volumes/Camera/Photos/IMG_0042.jpg
  ...

Matched by EXIF only (re-encoded/edited): 3
  /Volumes/Camera/Photos/IMG_0010.jpg
  ...

Matched by pHash only (visually similar): 1
  /Volumes/Camera/Photos/IMG_0099.jpg  [distance: 3]
```

### Design decisions

- **Summary at the top** — the most important information (counts) is immediately visible without scrolling.
- **All three categories in the file** — the file includes not just `missing` but also EXIF-only and pHash-only matches. These are files with different hashes that were found via alternative methods. They may need review (e.g., an EXIF-matched file might be a re-encoded copy worth keeping or discarding).
- **Desktop default** — places the file where it's immediately findable after a comparison run. Override with `--output` for scripted or non-macOS use.
- **OSError is non-fatal** — if the Desktop doesn't exist (Linux, headless), a warning is printed to stderr and the command still exits successfully with stdout output intact.

---

## pHash Threshold Change

The default Hamming distance threshold was reduced from **10** to **5**.

### Rationale

| Threshold | Behaviour |
|-----------|-----------|
| 10 | Matches images with up to 10 different bits out of 64 (~16%). Catches heavy re-encoding but risks false positives between genuinely different photos with similar tonal ranges. |
| **5** | Matches images with up to 5 different bits out of 64 (~8%). Catches typical JPEG re-encoding and HEIC→JPG conversion while keeping false positives very rare. |

A distance of ≤ 5 corresponds to images that are highly likely to be the same photo. Real re-encoding of a typical photograph shifts at most 2–4 bits. A distance of 6–10 starts to include different photos that happen to have similar average brightness or low-contrast content.

The constant `PHASH_THRESHOLD = 5` in `dbc.py` is the single tuning point. Pass `compare_records(..., phash_threshold=N)` to override programmatically.

---

## Dependencies Added

| Package | Purpose |
|---------|---------|
| `imagehash>=4.3` | pHash computation and comparison |
| `numpy` | Transitive dependency of imagehash |
| `scipy` | Transitive dependency of imagehash (DCT via `scipy.fft`) |
| `PyWavelets` | Transitive dependency of imagehash |

Install: `uv add imagehash` (pulls the rest automatically).

---

## Migration

Existing `.dbf.db` files use the old 4-column schema. Running `dbc` against them will fail with:

```
Error: .dbf.db: schema is outdated — re-run 'dbf' to rebuild.
```

Re-run `dbf` on each folder to rebuild the database with the new schema.

---

## Performance Notes

- **`dbf` build time**: pHash computation requires decoding each image (the dominant cost). This is done once per `dbf` run using multiprocessing. For a 10,000-image library, expect roughly 2–5× longer build time compared to the old hash-only approach.

- **`dbc` comparison time**: Pass 3 is O(n × m) — for each unmatched db2 record, scan all db1 phashes. For typical photo libraries (tens of thousands of images), this is fast enough in Python (~1M hash comparisons/second). For very large libraries (100K+), a BK-tree structure could reduce this to O(n log m).

- **Threshold tuning**: Lower the threshold (e.g., 5) for stricter matching (fewer false positives, may miss some valid matches). Raise it (e.g., 15) to catch more aggressively edited images (more false positives). The constant `PHASH_THRESHOLD = 10` in `dbc.py` is the tuning point.
