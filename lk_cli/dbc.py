import click
import datetime
import imagehash
import os
import sqlite3
from lk_cli.utils import get_version, get_pool


DB_NAME = ".dbf.db"
PHASH_THRESHOLD = 5


def load_db(db_path):
    """Load all records from a .dbf.db. Raises RuntimeError if schema is outdated."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT hash, name, created_at, camera_model, subsec_time, "
            "image_width, image_height, file_size, image_unique_id, camera_serial, phash "
            "FROM files"
        ).fetchall()
    except sqlite3.OperationalError as e:
        conn.close()
        raise RuntimeError(
            f"{db_path}: schema is outdated — re-run 'dbf' to rebuild. ({e})"
        ) from e
    conn.close()
    return rows


def compare_records(db1_records, db2_records, phash_threshold=PHASH_THRESHOLD):
    """
    Compare DB records from two folders.

    Pass 1 — Hash match: identical byte-for-byte copy (handles moves/renames).
    Pass 2 — EXIF match: same (camera_model, created_at, subsec_time) with a different hash.
              Sub-second precision prevents false matches between burst shots.
    Pass 3 — pHash match: perceptual hash within Hamming distance threshold.
              Catches re-encoded, format-converted, or lightly edited copies.

    Returns:
        missing    — names from db2 not found in db1 by any method
        exif_only  — (db2_name, db1_name) pairs matched only by EXIF
        phash_only — (db2_name, db1_name, distance) pairs matched only by pHash
    """
    def _f(row, idx):
        return row[idx] if len(row) > idx else None

    # Pass 1: exact content hash
    db1_hashes = {row[0] for row in db1_records if row[0]}

    # Pass 2: EXIF identity — camera model + capture time + sub-second
    db1_exif = {}
    for row in db1_records:
        name, created_at = _f(row, 1), _f(row, 2)
        camera_model, subsec_time = _f(row, 3), _f(row, 4)
        if camera_model and created_at:
            db1_exif.setdefault((camera_model, created_at, subsec_time), name)

    # Pass 3: perceptual hash
    db1_phashes = [
        (imagehash.hex_to_hash(_f(row, 10)), row[1])
        for row in db1_records
        if _f(row, 10)
    ]

    missing = []
    exif_only = []
    phash_only = []

    for row in db2_records:
        hash_, name = row[0], row[1]
        created_at, camera_model, subsec_time = _f(row, 2), _f(row, 3), _f(row, 4)
        ph = _f(row, 10)

        if hash_ in db1_hashes:
            continue

        if camera_model and created_at:
            key = (camera_model, created_at, subsec_time)
            if key in db1_exif:
                exif_only.append((name, db1_exif[key]))
                continue

        if ph:
            ph_obj = imagehash.hex_to_hash(ph)
            match = next(
                ((d_name, ph_obj - d_ph) for d_ph, d_name in db1_phashes
                 if (ph_obj - d_ph) <= phash_threshold),
                None,
            )
            if match:
                phash_only.append((name, match[0], match[1]))
                continue

        missing.append(name)

    return missing, exif_only, phash_only


def write_results(output_path, folder1, folder2, total_db2, hash_matched,
                  missing, exif_only, phash_only):
    """Write a summary header and file lists to output_path. Returns the resolved path."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "dbc Results",
        f"Generated:           {now}",
        f"Folder1 (reference): {folder1}",
        f"Folder2 (checked):   {folder2}",
        "",
        "Summary",
        "-" * 50,
        f"  Hash matches:   {hash_matched:5d}  (exact byte-for-byte copies)",
        f"  EXIF matches:   {len(exif_only):5d}  (same camera+time, different hash)",
        f"  pHash matches:  {len(phash_only):5d}  (visually similar, Hamming distance ≤ {PHASH_THRESHOLD})",
        f"  Missing:        {len(missing):5d}  (not found by any method)",
        f"  Total in folder2: {total_db2}",
        "",
    ]

    if missing:
        lines.append(f"Missing (not found by hash, EXIF, or pHash): {len(missing)}")
        for name in sorted(missing):
            lines.append(f"  {name}")
        lines.append("")

    if exif_only:
        lines.append(f"Matched by EXIF only (re-encoded/edited): {len(exif_only)}")
        for db2_name, _ in sorted(exif_only):
            lines.append(f"  {db2_name}")
        lines.append("")

    if phash_only:
        lines.append(f"Matched by pHash only (visually similar): {len(phash_only)}")
        for db2_name, _, dist in sorted(phash_only):
            lines.append(f"  {db2_name}  [distance: {dist}]")
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

    try:
        with get_pool() as pool:
            db1_records, db2_records = pool.map(load_db, [db1_path, db2_path])
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    missing, exif_only, phash_only = compare_records(db1_records, db2_records)

    hash_matched = len(db2_records) - len(missing) - len(exif_only) - len(phash_only)

    if missing:
        click.echo(f"Missing from {folder1} (not found by hash, EXIF, or pHash):")
        for name in sorted(missing):
            click.echo(f"  {name}")
        click.echo(f"Total missing: {len(missing)}")

    if exif_only:
        click.echo("Matched by EXIF only (different hash, same camera+time):")
        for db2_name, _ in sorted(exif_only):
            click.echo(f"  {db2_name}")

    if phash_only:
        click.echo("Matched by pHash only (visually similar, different hash+EXIF):")
        for db2_name, _, dist in sorted(phash_only):
            click.echo(f"  {db2_name}  [distance: {dist}]")

    if not missing and not exif_only and not phash_only:
        click.echo(
            f"All files in {folder2} exist in {folder1} ({hash_matched} by hash)."
        )
    elif not missing:
        parts = [f"{hash_matched} by hash"]
        if exif_only:
            parts.append(f"{len(exif_only)} by EXIF")
        if phash_only:
            parts.append(f"{len(phash_only)} by pHash")
        click.echo(
            f"All files in {folder2} accounted for in {folder1} "
            f"({', '.join(parts)})."
        )

    try:
        out_path = write_results(
            output, folder1, folder2, len(db2_records),
            hash_matched, missing, exif_only, phash_only,
        )
        click.echo(f"Results written to {out_path}")
    except OSError as e:
        click.echo(f"Warning: could not write results to {output}: {e}", err=True)
