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
        assert cols == {"hash", "name", "created_at", "camera_model"}

    def test_empty_folder_produces_no_db(self, tmp_path):
        invoke(tmp_path)
        assert not os.path.exists(str(tmp_path / DB_NAME))


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
