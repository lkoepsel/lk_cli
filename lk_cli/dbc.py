import click
import os
import sqlite3
from lk_cli.utils import get_version, get_pool


DB_NAME = ".dbf.db"


def load_db(db_path):
    """Load all records from a .dbf.db. Returns list of (hash, name, created_at, camera_model)."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT hash, name, created_at, camera_model FROM files"
    ).fetchall()
    conn.close()
    return rows


def compare_records(db1_records, db2_records):
    """
    Compare DB records from two folders.

    Pass 1 — Hash match: identical byte-for-byte copy (handles moves/renames).
    Pass 2 — EXIF match: same (camera_model, created_at) with a different hash.
              Requires both EXIF fields to be non-NULL. Indicates re-encoded/edited copies.

    Returns:
        missing   — names from db2 not found in db1 by any method
        exif_only — (db2_name, db1_name) pairs matched only by EXIF (different hash)
    """
    db1_hashes = {row[0] for row in db1_records if row[0]}

    db1_exif = {}  # (camera_model, created_at) -> name
    for hash_, name, created_at, camera_model in db1_records:
        if camera_model and created_at:
            db1_exif[(camera_model, created_at)] = name

    missing = []
    exif_only = []

    for hash_, name, created_at, camera_model in db2_records:
        if hash_ in db1_hashes:
            continue

        if camera_model and created_at:
            key = (camera_model, created_at)
            if key in db1_exif:
                exif_only.append((name, db1_exif[key]))
                continue

        missing.append(name)

    return missing, exif_only


@click.command()
@click.version_option(get_version(), prog_name="dbc")
@click.argument("folder1", type=click.Path(exists=True, file_okay=False))
@click.argument("folder2", type=click.Path(exists=True, file_okay=False))
def dbc(folder1, folder2):
    """
    dbc: database compare
    Find files in folder2's .dbf.db that are missing from folder1's .dbf.db.
    Matching is done in two passes:

    \b
    Pass 1 — Hash match: identical byte-for-byte copy (handles moves/renames).
    Pass 2 — EXIF match: same camera model + creation time with a different hash
              (handles re-exports, edits, or format conversions).

    Files not matched by either method are reported as missing.
    Both folders must already have a .dbf.db created by the dbf command.
    """
    db1_path = os.path.join(folder1, DB_NAME)
    db2_path = os.path.join(folder2, DB_NAME)

    if not os.path.exists(db1_path):
        click.echo(f"Error: No {DB_NAME} found in {folder1}", err=True)
        raise SystemExit(1)

    if not os.path.exists(db2_path):
        click.echo(f"Error: No {DB_NAME} found in {folder2}", err=True)
        raise SystemExit(1)

    with get_pool() as pool:
        db1_records, db2_records = pool.map(load_db, [db1_path, db2_path])

    missing, exif_only = compare_records(db1_records, db2_records)

    hash_matched = len(db2_records) - len(missing) - len(exif_only)

    if missing:
        click.echo(f"Missing from {folder1} (not found by hash or EXIF):")
        for name in sorted(missing):
            click.echo(f"  {name}")
        click.echo(f"Total missing: {len(missing)}")

    if exif_only:
        click.echo("Matched by EXIF only (different hash, same camera+time):")
        for db2_name, _ in sorted(exif_only):
            click.echo(f"  {db2_name}")

    if not missing and not exif_only:
        click.echo(
            f"All files in {folder2} exist in {folder1} ({hash_matched} by hash)."
        )
    elif not missing:
        click.echo(
            f"All files in {folder2} accounted for in {folder1} "
            f"({hash_matched} by hash, {len(exif_only)} by EXIF)."
        )
