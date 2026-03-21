import click
import os
import sqlite3
from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener
from lk_cli.utils import hash_file, get_version, get_pool, dot_file

register_heif_opener()

DB_NAME = ".dbf.db"


def process_image(filepath):
    """Hash and extract EXIF from a single file.

    Returns (is_image, file_hash, name, created_at, camera_model).
    is_image=False for non-image files or unreadable files.
    """
    name = filepath
    file_hash = hash_file(filepath)
    if file_hash is None:
        return (False, None, name, None, None)

    try:
        with Image.open(filepath) as img:
            exif = img.getexif()
            # Model is in IFD0; DateTimeOriginal is in the Exif sub-IFD (0x8769)
            camera_model = exif.get(272)
            created_at = exif.get(36867) or exif.get_ifd(0x8769).get(36867)
        return (True, file_hash, name, created_at, camera_model)
    except (UnidentifiedImageError, OSError, Exception):
        return (False, file_hash, name, None, None)


@click.command()
@click.version_option(get_version(), prog_name="dbf")
@click.argument("folder", type=click.Path(exists=True, file_okay=False))
def dbf(folder):
    """
    dbf: database of files
    Build an SQLite database of image files containing hash, filename,
    EXIF creation date/time, and camera model. Non-image files are skipped
    and printed to stdout. Database is stored in the folder as .dbf.db.
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
        results = pool.map(process_image, all_filepaths)

    db_path = os.path.join(folder, DB_NAME)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            hash         TEXT,
            name         TEXT,
            created_at   TEXT,
            camera_model TEXT
        )
    """)

    image_count = 0
    for is_image, file_hash, name, created_at, camera_model in results:
        if not is_image:
            click.echo(f"Skipping non-image: {name}")
        else:
            conn.execute(
                "INSERT INTO files VALUES (?, ?, ?, ?)",
                (file_hash, name, created_at, camera_model),
            )
            image_count += 1

    conn.commit()
    conn.close()
    click.echo(f"Wrote {image_count} image(s) to {db_path}")
