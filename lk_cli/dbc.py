import click
import imagehash
import os
import sqlite3
from lk_cli.utils import get_version, get_pool, DB_NAME, ImageRecord
PHASH_THRESHOLD = 5


def read_db_version(db_path):
    """Read the created_by_version from a database's meta table.

    Returns the version string, or None if the meta table is absent or the
    key is not present (e.g., a database built by an older version of dbf).
    """
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'created_by_version'"
        ).fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def load_db(db_path):
    """Load all records from a .dbf.db. Raises RuntimeError if schema is outdated."""
    conn = sqlite3.connect(db_path)
    cols = ", ".join(ImageRecord._fields)
    try:
        rows = conn.execute(f"SELECT {cols} FROM files").fetchall()
    except sqlite3.OperationalError as e:
        conn.close()
        raise RuntimeError(
            f"{db_path}: schema is outdated — re-run 'dbf' to rebuild. ({e})"
        ) from e
    conn.close()
    return [ImageRecord(*row) for row in rows]


def compare_records(db1_records, db2_records, phash_threshold=PHASH_THRESHOLD):
    """
    Compare DB records from two folders.

    Pass 1 — Hash match: identical byte-for-byte copy (handles moves/renames).
    Pass 2 — Image hash match: same decoded pixel content, metadata differs.
              Catches format conversions and copies with differing metadata.
    Pass 3 — EXIF match: same (camera_model, created_at, subsec_time).
              Sub-second precision prevents false matches between burst shots.
    Pass 4 — pHash match: perceptual hash within Hamming distance threshold.
              Catches re-encoded, lightly edited, or resized copies.

    Returns:
        missing    — names from db2 not found in db1 by any method
        image_only — (db2_name, db1_name) pairs matched only by image hash
        exif_only  — (db2_name, db1_name) pairs matched only by EXIF
        phash_only — (db2_name, db1_name, distance) pairs matched only by pHash
        hash_only  — names from db2 matched by exact file hash (Pass 1)
    """
    # Pass 1: exact file hash
    db1_hashes = {row.hash for row in db1_records if row.hash}

    # Pass 2: image content hash — same pixels, different metadata/compression
    db1_image_hashes = {}
    for row in db1_records:
        if row.image_hash:
            db1_image_hashes.setdefault(row.image_hash, row.name)

    # Pass 3: EXIF identity — camera model + capture time + sub-second
    db1_exif = {}
    for row in db1_records:
        if row.camera_model and row.created_at:
            db1_exif.setdefault(
                (row.camera_model, row.created_at, row.subsec_time),
                row.name,
            )

    # Pass 4: perceptual hash
    db1_phashes = [
        (imagehash.hex_to_hash(row.phash), row.name)
        for row in db1_records
        if row.phash
    ]

    missing = []
    image_only = []
    exif_only = []
    phash_only = []
    hash_only = []

    for row in db2_records:
        if row.hash in db1_hashes:
            hash_only.append(row.name)
            continue

        if row.image_hash and row.image_hash in db1_image_hashes:
            image_only.append((row.name, db1_image_hashes[row.image_hash]))
            continue

        if row.camera_model and row.created_at:
            key = (row.camera_model, row.created_at, row.subsec_time)
            if key in db1_exif:
                exif_only.append((row.name, db1_exif[key]))
                continue

        if row.phash:
            ph_obj = imagehash.hex_to_hash(row.phash)
            match = next(
                ((d_name, ph_obj - d_ph) for d_ph, d_name in db1_phashes
                 if (ph_obj - d_ph) <= phash_threshold),
                None,
            )
            if match:
                phash_only.append((row.name, match[0], match[1]))
                continue

        missing.append(row.name)

    return missing, image_only, exif_only, phash_only, hash_only


def write_results(output_path, missing, image_only, exif_only, phash_only,
                  hash_only=None, folder1=None, folder2=None,
                  phash_threshold=PHASH_THRESHOLD):
    """Write categorised file lists to output_path. Returns the resolved path."""
    lines = []

    if folder1 is not None or folder2 is not None:
        lines.append(f"Folder1 (reference): {folder1 or ''}")
        lines.append(f"Folder2 (checked):   {folder2 or ''}")
        lines.append("")

    if hash_only:
        lines.append(f"Hash matches: {len(hash_only)}")
        for name in sorted(hash_only):
            lines.append(f"  {name}")
        lines.append("")

    if image_only:
        lines.append(f"Image hash matches: {len(image_only)}")
        for db2_name, _ in sorted(image_only):
            lines.append(f"  {db2_name}")
        lines.append("")

    if exif_only:
        lines.append(f"EXIF matches (re-encoded/edited): {len(exif_only)}")
        for db2_name, _ in sorted(exif_only):
            lines.append(f"  {db2_name}")
        lines.append("")

    if phash_only:
        lines.append(f"pHash matches (Hamming distance ≤ {phash_threshold}): {len(phash_only)}")
        for db2_name, _, dist in sorted(phash_only):
            lines.append(f"  {db2_name}  [distance: {dist}]")
        lines.append("")

    if missing:
        lines.append(f"Missing (not found by hash, EXIF, or pHash): {len(missing)}")
        for name in sorted(missing):
            lines.append(f"  {name}")
        lines.append("")

    resolved = os.path.expanduser(output_path)
    with open(resolved, "w") as f:
        f.write("\n".join(lines) + "\n")
    return resolved


@click.command()
@click.version_option(get_version(), prog_name="dbc")
@click.option(
    "--output",
    default="~/Desktop/dbc_results.txt",
    show_default=True,
    help="Output file for results summary and file lists.",
)
@click.argument("folder1", type=click.Path(exists=True, file_okay=False))
@click.argument("folder2", type=click.Path(exists=True, file_okay=False))
def dbc(folder1, folder2, output):
    """
    dbc: database compare
    Find files in folder2's .dbf.db that are missing from folder1's .dbf.db.
    Matching is done in three passes:

    \b
    Pass 1 — Hash match: identical byte-for-byte copy (handles moves/renames).
    Pass 2 — EXIF match: same camera model + creation time + sub-second (burst-safe).
    Pass 3 — pHash match: perceptual similarity within Hamming distance 5.
              Catches re-exports, format conversions (HEIC→JPG), or minor edits.

    Files not matched by any method are reported as missing.
    Both folders must already have a .dbf.db created by the dbf command.
    Results are written to a file (default: ~/Desktop/dbc_results.txt).
    """
    db1_path = os.path.join(folder1, DB_NAME)
    db2_path = os.path.join(folder2, DB_NAME)

    if not os.path.exists(db1_path):
        click.echo(f"Error: No {DB_NAME} found in {folder1}", err=True)
        raise SystemExit(1)

    if not os.path.exists(db2_path):
        click.echo(f"Error: No {DB_NAME} found in {folder2}", err=True)
        raise SystemExit(1)

    db1_version = read_db_version(db1_path)
    db2_version = read_db_version(db2_path)
    dbc_version = get_version()

    try:
        with get_pool() as pool:
            db1_records, db2_records = pool.map(load_db, [db1_path, db2_path])
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    missing, image_only, exif_only, phash_only, hash_only = compare_records(
        db1_records, db2_records
    )

    # ── terminal: summary only ────────────────────────────────────────────────
    if dbc_version:
        click.echo(f"dbc version:         {dbc_version}")
    click.echo(f"Folder1 (reference): {folder1}")
    if db1_version:
        click.echo(f"  dbf version:       {db1_version}")
    click.echo(f"Folder2 (checked):   {folder2}")
    if db2_version:
        click.echo(f"  dbf version:       {db2_version}")
    click.echo("")
    click.echo("Summary")
    click.echo("-" * 50)
    click.echo(f"  Total in folder1: {len(db1_records)}")
    click.echo(f"  Total in folder2: {len(db2_records)}")
    if len(db2_records) > len(db1_records):
        excess = len(db2_records) - len(db1_records)
        click.echo(f"  Note: folder2 (checked) has {excess} more photo(s) than folder1 (reference)")
    click.echo(f"  Hash matches:   {len(hash_only):5d}  (exact byte-for-byte copies)")
    click.echo(f"  Image matches:  {len(image_only):5d}  (same pixels, metadata differs)")
    click.echo(f"  EXIF matches:   {len(exif_only):5d}  (same camera+time, different pixels)")
    click.echo(f"  pHash matches:  {len(phash_only):5d}  (visually similar, Hamming distance ≤ {PHASH_THRESHOLD})")
    click.echo(f"  Missing:        {len(missing):5d}  (in folder2, not found in folder1 by any method)")

    try:
        out_path = write_results(
            output, missing, image_only, exif_only, phash_only,
            hash_only=hash_only, folder1=folder1, folder2=folder2,
            phash_threshold=PHASH_THRESHOLD,
        )
        click.echo(f"Results written to {out_path}")
    except OSError as e:
        click.echo(f"Warning: could not write results to {output}: {e}", err=True)
