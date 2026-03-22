import click
import imagehash
import os
import sqlite3
import sys
from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener
from lk_cli.utils import hash_file, get_version, get_pool, dot_file

register_heif_opener()

DB_NAME = ".dbf.db"
_EXIF_IFD = 0x8769


def process_image(filepath):
    """Hash, EXIF, dimensions, and perceptual hash for one file.

    Returns (is_image, hash, name, created_at, camera_model,
             subsec_time, image_width, image_height, file_size,
             image_unique_id, camera_serial, phash).
    is_image=False for non-image files or unreadable files.
    """
    name = filepath
    file_hash = hash_file(filepath)
    if file_hash is None:
        return (False, None, name, None, None, None, None, None, None, None, None, None)

    file_size = os.path.getsize(filepath)

    try:
        with Image.open(filepath) as img:
            width, height = img.width, img.height
            exif = img.getexif()
            ifd = exif.get_ifd(_EXIF_IFD)
            camera_model = exif.get(272)
            created_at = exif.get(36867) or ifd.get(36867)
            subsec_time = ifd.get(37521)
            image_unique_id = ifd.get(42016)
            camera_serial = ifd.get(42033) or exif.get(42033)
            ph = str(imagehash.phash(img))
        return (
            True, file_hash, name, created_at, camera_model,
            subsec_time, width, height, file_size,
            image_unique_id, camera_serial, ph,
        )
    except (UnidentifiedImageError, OSError, Exception):
        return (False, file_hash, name, None, None, None, None, None, file_size, None, None, None)


@click.command()
@click.version_option(get_version(), prog_name="dbf")
@click.argument("folder", type=click.Path(exists=True, file_okay=False))
def dbf(folder):
    """
    dbf: database of files
    Build an SQLite database of image files containing hash, filename,
    EXIF fields (creation time, sub-second, camera model/serial, image ID),
    pixel dimensions, file size, and a perceptual hash (pHash).
    Non-image files are skipped and printed to stdout.
    Database is stored in the folder as .dbf.db.
    Uses multiprocessing and xxHash64 for speed.

    """
    all_filepaths = []
    for root, _, files in os.walk(folder):
        for file in files:
            if not dot_file.match(file):
                all_filepaths.append(os.path.join(root, file))

    if not all_filepaths:
        click.echo("No files found.")
        return

    with get_pool() as pool:
        with click.progressbar(
            pool.imap_unordered(process_image, all_filepaths),
            length=len(all_filepaths),
            label="Processing images",
            file=sys.stderr,
        ) as bar:
            results = list(bar)

    db_path = os.path.join(folder, DB_NAME)
    conn = sqlite3.connect(db_path)
    conn.execute("DROP TABLE IF EXISTS files")
    conn.execute("""
        CREATE TABLE files (
            hash             TEXT,
            name             TEXT,
            created_at       TEXT,
            camera_model     TEXT,
            subsec_time      TEXT,
            image_width      INTEGER,
            image_height     INTEGER,
            file_size        INTEGER,
            image_unique_id  TEXT,
            camera_serial    TEXT,
            phash            TEXT
        )
    """)

    image_count = 0
    for row in results:
        if not row[0]:
            click.echo(f"Skipping non-image: {row[2]}")
        else:
            conn.execute(
                "INSERT INTO files VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row[1:],
            )
            image_count += 1

    conn.commit()
    conn.close()
    click.echo(f"Wrote {image_count} image(s) to {db_path}")
