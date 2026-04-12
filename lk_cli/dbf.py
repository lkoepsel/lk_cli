import click
import hashlib
import imagehash
import os
import sqlite3
import struct
import sys
from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener
from lk_cli.utils import (
    hash_file, get_version, get_pool, dot_file, DB_NAME,
    create_db_schema, ImageRecord,
)

register_heif_opener()
_EXIF_IFD = 0x8769
_NIKON_MARKER = b"Nikon\x00"


def _nikon_memory_card(ifd):
    """Extract Memory Card Number from a Nikon MakerNote (ExifIFD dict).

    Returns a string like "0" or "1", or None if the data is unavailable,
    the camera is not Nikon, or parsing fails for any reason.

    The Memory Card Number lives in the Nikon MakerNote FileInfo binary
    block (MakerNote IFD tag 0x00B8), at byte offset 4 after the 4-byte
    version header "0100".  Offsets within the MakerNote TIFF structure
    are relative to the start of the embedded TIFF header (byte 8 of the
    MakerNote, after the 6-byte "Nikon\\x00" signature and 2-byte version).
    """
    try:
        mn = ifd.get(37500)  # 37500 = MakerNote
        if not isinstance(mn, bytes) or not mn.startswith(_NIKON_MARKER):
            return None

        t = 10  # TIFF header starts after "Nikon\x00" (6) + version (2) + padding (2)
        bo = mn[t:t + 2]
        endian = ">" if bo == b"MM" else "<" if bo == b"II" else None
        if not endian:
            return None
        if struct.unpack(f"{endian}H", mn[t + 2:t + 4])[0] != 42:
            return None

        ifd_off = struct.unpack(f"{endian}I", mn[t + 4:t + 8])[0]
        pos = t + ifd_off
        num = struct.unpack(f"{endian}H", mn[pos:pos + 2])[0]
        pos += 2

        for _ in range(num):
            tag = struct.unpack(f"{endian}H", mn[pos:pos + 2])[0]
            # skip type (2 bytes), read count (4 bytes) and raw value/offset (4 bytes)
            count = struct.unpack(f"{endian}I", mn[pos + 4:pos + 8])[0]
            raw = mn[pos + 8:pos + 12]
            pos += 12
            if tag == 0x00B8:  # FileInfo (Nikon MakerNote tag 0x00B8)
                fi_off = struct.unpack(f"{endian}I", raw)[0]
                fi = mn[t + fi_off:]
                if len(fi) >= 6 and fi[:4] == b"0100":
                    return str(struct.unpack(f"{endian}H", fi[4:6])[0])
                return None
        return None
    except Exception:
        return None


def process_image(filepath):
    """Hash, EXIF, dimensions, perceptual hash, and memory card number for one file.

    Returns (is_image, *ImageRecord fields).
    is_image=False for non-image files or unreadable files.
    """
    name = filepath
    file_hash = hash_file(filepath)
    n = len(ImageRecord._fields)
    if file_hash is None:
        return (False,) + (None,) * n

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
            memory_card_number = _nikon_memory_card(ifd)
            image_hash = hashlib.sha256(img.convert("RGB").tobytes()).hexdigest()
        return (
            True, file_hash, name, created_at, camera_model,
            subsec_time, width, height, file_size,
            image_unique_id, camera_serial, ph, memory_card_number, image_hash,
        )
    except Exception:
        return (False, file_hash, name) + (None,) * (n - 2)


@click.command()
@click.version_option(get_version(), prog_name="dbf")
@click.argument("folder", type=click.Path(exists=True, file_okay=False))
def dbf(folder):
    """
    dbf: database of files
    Build an SQLite database of image files containing hash, filename,
    EXIF fields (creation time, sub-second, camera model/serial, image ID),
    pixel dimensions, file size, perceptual hash (pHash), and memory card
    number (Nikon dual-slot cameras).
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
    create_db_schema(conn)
    conn.execute("INSERT INTO meta VALUES (?, ?)", ("created_by_version", get_version()))

    placeholders = ", ".join("?" * len(ImageRecord._fields))
    image_count = 0
    for row in results:
        if not row[0]:
            click.echo(f"Skipping non-image: {row[2]}")
        else:
            conn.execute(f"INSERT INTO files VALUES ({placeholders})", row[1:])
            image_count += 1

    conn.commit()
    conn.close()
    click.echo(f"Wrote {image_count} image(s) to {db_path}")
