import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from PIL import Image


DB_NAME = ".dbf.db"


# ── helpers ───────────────────────────────────────────────────────────────────

def make_plain_image(path):
    """Create a minimal JPEG with no EXIF data."""
    img = Image.new("RGB", (10, 10), color="red")
    img.save(path, "JPEG")
    return path


def make_image_with_exif(path, date_time="2024:01:15 10:30:00", model="TestCamera X1"):
    """Create a JPEG with DateTimeOriginal and Model EXIF fields."""
    img = Image.new("RGB", (10, 10), color="blue")
    exif = img.getexif()
    exif[272] = model                          # Model lives in IFD0
    exif.get_ifd(0x8769)[36867] = date_time    # DateTimeOriginal lives in Exif sub-IFD
    img.save(path, "JPEG", exif=exif.tobytes())
    return path


def make_image_with_subsec(path, date_time="2024:01:15 10:30:00", model="BurstCam", subsec="50"):
    """Create a JPEG with DateTimeOriginal, Model, and SubSecTimeOriginal EXIF fields."""
    img = Image.new("RGB", (20, 20), color="green")
    exif = img.getexif()
    exif[272] = model
    ifd = exif.get_ifd(0x8769)
    ifd[36867] = date_time
    ifd[37521] = subsec   # SubSecTimeOriginal
    img.save(path, "JPEG", exif=exif.tobytes())
    return path


def open_db(folder):
    return sqlite3.connect(os.path.join(folder, DB_NAME))


def invoke(tmp_path):
    from lk_cli.dbf import dbf
    return CliRunner().invoke(dbf, [str(tmp_path)])


# ── tests ─────────────────────────────────────────────────────────────────────

class TestDbfCreation:
    def test_db_file_created_in_folder(self, tmp_path):
        make_plain_image(str(tmp_path / "a.jpg"))
        invoke(tmp_path)
        assert os.path.exists(str(tmp_path / DB_NAME))

    def test_db_has_correct_columns(self, tmp_path):
        make_plain_image(str(tmp_path / "a.jpg"))
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        cols = {row[1] for row in conn.execute("PRAGMA table_info(files)")}
        conn.close()
        assert cols == {
            "hash", "name", "created_at", "camera_model",
            "subsec_time", "image_width", "image_height", "file_size",
            "image_unique_id", "camera_serial", "phash", "memory_card_number",
            "image_hash",
        }

    def test_empty_folder_produces_no_db(self, tmp_path):
        invoke(tmp_path)
        assert not os.path.exists(str(tmp_path / DB_NAME))

    def test_rerun_replaces_existing_db(self, tmp_path):
        make_plain_image(str(tmp_path / "a.jpg"))
        invoke(tmp_path)
        make_plain_image(str(tmp_path / "b.jpg"))
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        conn.close()
        assert count == 2  # only two images, not three from two runs


class TestImageRecording:
    def test_image_recorded_with_full_path(self, tmp_path):
        path = make_plain_image(str(tmp_path / "photo.jpg"))
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        names = [r[0] for r in conn.execute("SELECT name FROM files")]
        conn.close()
        assert path in names

    def test_image_recorded_with_correct_hash(self, tmp_path):
        from lk_cli.utils import hash_file
        path = make_plain_image(str(tmp_path / "photo.jpg"))
        invoke(tmp_path)
        expected_hash = hash_file(path)
        conn = open_db(str(tmp_path))
        hashes = [r[0] for r in conn.execute("SELECT hash FROM files")]
        conn.close()
        assert expected_hash in hashes

    def test_multiple_images_all_recorded(self, tmp_path):
        make_plain_image(str(tmp_path / "a.jpg"))
        make_plain_image(str(tmp_path / "b.jpg"))
        make_plain_image(str(tmp_path / "c.jpg"))
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        conn.close()
        assert count == 3


class TestExifData:
    def test_exif_date_and_model_stored(self, tmp_path):
        path = make_image_with_exif(
            str(tmp_path / "shot.jpg"),
            date_time="2024:06:21 08:15:00",
            model="Canon EOS R5",
        )
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        row = conn.execute(
            "SELECT created_at, camera_model FROM files WHERE name = ?", (path,)
        ).fetchone()
        conn.close()
        assert row[0] == "2024:06:21 08:15:00"
        assert row[1] == "Canon EOS R5"

    def test_image_without_exif_has_null_fields(self, tmp_path):
        path = make_plain_image(str(tmp_path / "no_exif.jpg"))
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        row = conn.execute(
            "SELECT created_at, camera_model FROM files WHERE name = ?", (path,)
        ).fetchone()
        conn.close()
        assert row[0] is None
        assert row[1] is None

    def test_subsec_time_stored_when_present(self, tmp_path):
        path = make_image_with_subsec(str(tmp_path / "burst.jpg"), subsec="75")
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        row = conn.execute(
            "SELECT subsec_time FROM files WHERE name = ?", (path,)
        ).fetchone()
        conn.close()
        assert row[0] == "75"

    def test_subsec_time_null_without_exif(self, tmp_path):
        path = make_plain_image(str(tmp_path / "plain.jpg"))
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        row = conn.execute(
            "SELECT subsec_time FROM files WHERE name = ?", (path,)
        ).fetchone()
        conn.close()
        assert row[0] is None


class TestImageHashField:
    def test_image_hash_stored_and_non_null(self, tmp_path):
        path = make_plain_image(str(tmp_path / "a.jpg"))
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        row = conn.execute(
            "SELECT image_hash FROM files WHERE name = ?", (path,)
        ).fetchone()
        conn.close()
        assert row[0] is not None
        assert len(row[0]) == 64  # SHA-256 hex = 64 chars

    def test_identical_content_same_image_hash(self, tmp_path):
        img = Image.new("RGB", (64, 64), color="blue")
        img.save(str(tmp_path / "a.jpg"), "JPEG")
        img.save(str(tmp_path / "b.jpg"), "JPEG")
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        hashes = [r[0] for r in conn.execute("SELECT image_hash FROM files ORDER BY name")]
        conn.close()
        assert hashes[0] == hashes[1]

    def test_different_content_different_image_hash(self, tmp_path):
        Image.new("RGB", (10, 10), color="red").save(str(tmp_path / "a.jpg"), "JPEG")
        Image.new("RGB", (10, 10), color="blue").save(str(tmp_path / "b.jpg"), "JPEG")
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        hashes = [r[0] for r in conn.execute("SELECT image_hash FROM files ORDER BY name")]
        conn.close()
        assert hashes[0] != hashes[1]


class TestNewFields:
    def test_phash_stored_and_non_null(self, tmp_path):
        path = make_plain_image(str(tmp_path / "a.jpg"))
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        row = conn.execute(
            "SELECT phash FROM files WHERE name = ?", (path,)
        ).fetchone()
        conn.close()
        assert row[0] is not None
        assert len(row[0]) > 0

    def test_phash_is_valid_hex(self, tmp_path):
        import imagehash
        make_plain_image(str(tmp_path / "a.jpg"))
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        ph = conn.execute("SELECT phash FROM files").fetchone()[0]
        conn.close()
        # Should be parseable by imagehash without error
        imagehash.hex_to_hash(ph)

    def test_dimensions_stored_correctly(self, tmp_path):
        img = Image.new("RGB", (640, 480), color="red")
        path = str(tmp_path / "sized.jpg")
        img.save(path, "JPEG")
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        row = conn.execute(
            "SELECT image_width, image_height FROM files WHERE name = ?", (path,)
        ).fetchone()
        conn.close()
        assert row[0] == 640
        assert row[1] == 480

    def test_file_size_stored_correctly(self, tmp_path):
        path = make_plain_image(str(tmp_path / "a.jpg"))
        invoke(tmp_path)
        expected_size = os.path.getsize(path)
        conn = open_db(str(tmp_path))
        row = conn.execute(
            "SELECT file_size FROM files WHERE name = ?", (path,)
        ).fetchone()
        conn.close()
        assert row[0] == expected_size

    def test_identical_content_has_zero_phash_distance(self, tmp_path):
        import imagehash
        # Save the same image twice — identical visual content must yield distance 0
        img = Image.new("RGB", (64, 64), color="red")
        img.save(str(tmp_path / "a.jpg"), "JPEG")
        img.save(str(tmp_path / "b.jpg"), "JPEG")
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        hashes = [r[0] for r in conn.execute("SELECT phash FROM files ORDER BY name")]
        conn.close()
        h1 = imagehash.hex_to_hash(hashes[0])
        h2 = imagehash.hex_to_hash(hashes[1])
        assert (h1 - h2) == 0


class TestNonImageHandling:
    def test_non_image_not_in_db(self, tmp_path):
        make_plain_image(str(tmp_path / "real.jpg"))
        (tmp_path / "notes.txt").write_text("not an image")
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        names = [r[0] for r in conn.execute("SELECT name FROM files")]
        conn.close()
        assert not any("notes.txt" in n for n in names)

    def test_non_image_printed_to_stdout(self, tmp_path):
        make_plain_image(str(tmp_path / "real.jpg"))
        (tmp_path / "notes.txt").write_text("not an image")
        result = invoke(tmp_path)
        assert "notes.txt" in result.output

    def test_dotfiles_not_processed(self, tmp_path):
        real = make_plain_image(str(tmp_path / "real.jpg"))
        make_plain_image(str(tmp_path / ".hidden.jpg"))
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        names = [r[0] for r in conn.execute("SELECT name FROM files")]
        conn.close()
        assert not any(".hidden.jpg" in n for n in names)
        assert real in names


class TestHeicSupport:
    def test_heic_recorded_in_db(self, tmp_path):
        from pillow_heif import register_heif_opener
        register_heif_opener()
        img = Image.new("RGB", (10, 10), color="green")
        path = str(tmp_path / "photo.heic")
        img.save(path, format="HEIF")
        result = invoke(tmp_path)
        assert "Skipping non-image: photo.heic" not in result.output
        conn = open_db(str(tmp_path))
        names = [r[0] for r in conn.execute("SELECT name FROM files")]
        conn.close()
        assert path in names

    def test_heic_not_skipped_as_non_image(self, tmp_path):
        from pillow_heif import register_heif_opener
        register_heif_opener()
        img = Image.new("RGB", (10, 10), color="green")
        img.save(str(tmp_path / "photo.heic"), format="HEIF")
        result = invoke(tmp_path)
        assert "Skipping non-image" not in result.output


class TestProcessImageExceptionHandling:
    def test_except_clause_not_redundant(self):
        """Exception must not appear alongside specific types in the except clause."""
        import ast
        import inspect
        import textwrap
        from lk_cli.dbf import process_image

        source = textwrap.dedent(inspect.getsource(process_image))
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type and isinstance(node.type, ast.Tuple):
                    names = [n.id for n in ast.walk(node.type) if isinstance(n, ast.Name)]
                    assert "Exception" not in names, (
                        f"Redundant except clause: 'Exception' listed alongside {names!r}. "
                        "Use 'except Exception:' alone."
                    )

    def test_os_error_returns_not_image(self, tmp_path):
        """An OSError from Image.open must yield is_image=False, not crash."""
        from lk_cli.dbf import process_image
        path = make_plain_image(str(tmp_path / "a.jpg"))
        with patch("lk_cli.dbf.Image.open", side_effect=OSError("read error")):
            result = process_image(path)
        assert result[0] is False

    def test_unidentified_image_error_returns_not_image(self, tmp_path):
        """An UnidentifiedImageError must yield is_image=False, not crash."""
        from PIL import UnidentifiedImageError
        from lk_cli.dbf import process_image
        path = make_plain_image(str(tmp_path / "a.jpg"))
        with patch("lk_cli.dbf.Image.open", side_effect=UnidentifiedImageError("not an image")):
            result = process_image(path)
        assert result[0] is False

    def test_phash_error_returns_not_image(self, tmp_path):
        """Any exception from imagehash.phash must yield is_image=False, not crash."""
        from lk_cli.dbf import process_image
        path = make_plain_image(str(tmp_path / "a.jpg"))
        with patch("lk_cli.dbf.imagehash.phash", side_effect=ValueError("phash failed")):
            result = process_image(path)
        assert result[0] is False


def make_nikon_maker_note(card_number):
    """Build minimal valid Nikon MakerNote bytes with the given card number (0-based raw).

    Layout: b"Nikon\\x00" (6) + version (2) + padding (2) + TIFF header + IFD + file_info
    The TIFF header starts at byte 10 (matching real NEF files).
    file_info offset from tiff_start = 8 (ifd_off) + 2 (num) + 12 (entry) + 4 (next) = 26
    """
    import struct
    e = ">"
    file_info = b"0100" + struct.pack(f"{e}H", card_number) + b"\x00" * 10
    tiff = (
        b"MM"
        + struct.pack(f"{e}H", 42)
        + struct.pack(f"{e}I", 8)             # IFD at offset 8 from tiff_start
        + struct.pack(f"{e}H", 1)             # 1 IFD entry
        + struct.pack(f"{e}H", 0x00B8)        # tag: FileInfo (Nikon MakerNote 0x00B8)
        + struct.pack(f"{e}H", 7)             # type: UNDEFINED
        + struct.pack(f"{e}I", len(file_info))# count
        + struct.pack(f"{e}I", 26)            # offset from tiff_start
        + struct.pack(f"{e}I", 0)             # next IFD
    )
    return b"Nikon\x00\x02\x10\x00\x00" + tiff + file_info


class TestVersionTracking:
    def test_version_stored_in_meta(self, tmp_path):
        from lk_cli.utils import get_version
        make_plain_image(str(tmp_path / "a.jpg"))
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'created_by_version'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == get_version()


class TestNikonMemoryCard:
    def test_returns_card_number_string(self):
        from lk_cli.dbf import _nikon_memory_card
        mn = make_nikon_maker_note(0)
        assert _nikon_memory_card({37500: mn}) == "0"

    def test_card_one_returns_one(self):
        from lk_cli.dbf import _nikon_memory_card
        mn = make_nikon_maker_note(1)
        assert _nikon_memory_card({37500: mn}) == "1"

    def test_non_nikon_returns_none(self):
        from lk_cli.dbf import _nikon_memory_card
        assert _nikon_memory_card({37500: b"FUJIFILM\x00\x00"}) is None

    def test_no_makernote_returns_none(self):
        from lk_cli.dbf import _nikon_memory_card
        assert _nikon_memory_card({}) is None

    def test_non_bytes_returns_none(self):
        from lk_cli.dbf import _nikon_memory_card
        assert _nikon_memory_card({37500: "not bytes"}) is None

    def test_memory_card_stored_in_db(self, tmp_path):
        """After dbf run, memory_card_number column must exist in the schema."""
        make_plain_image(str(tmp_path / "a.jpg"))
        invoke(tmp_path)
        conn = open_db(str(tmp_path))
        cols = {row[1] for row in conn.execute("PRAGMA table_info(files)")}
        conn.close()
        assert "memory_card_number" in cols


class TestMultiprocessing:
    def test_pool_is_used(self, tmp_path):
        from lk_cli.dbf import process_image
        make_plain_image(str(tmp_path / "a.jpg"))
        with patch("lk_cli.dbf.get_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_get_pool.return_value.__enter__ = lambda s: mock_pool
            mock_get_pool.return_value.__exit__ = lambda s, *a: None
            mock_pool.map.side_effect = lambda f, items: [process_image(i) for i in items]
            CliRunner().invoke(__import__("lk_cli.dbf", fromlist=["dbf"]).dbf, [str(tmp_path)])
        mock_get_pool.assert_called_once()
