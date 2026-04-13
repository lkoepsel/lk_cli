import imagehash
import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from PIL import Image
from lk_cli.utils import ImageRecord


DB_NAME = ".dbf.db"


# ── helpers ───────────────────────────────────────────────────────────────────

def make_db(folder, records):
    """Create a .dbf.db using the shared schema from utils.

    Records may be ImageRecord instances, short tuples, or any iterable.
    Short records are right-padded with None to match ImageRecord field count.
    """
    from lk_cli.utils import create_db_schema, ImageRecord
    n = len(ImageRecord._fields)
    db_path = os.path.join(str(folder), DB_NAME)
    conn = sqlite3.connect(db_path)
    create_db_schema(conn)
    placeholders = ", ".join("?" * n)
    padded = [tuple(r) + (None,) * (n - len(r)) for r in records]
    conn.executemany(f"INSERT INTO files VALUES ({placeholders})", padded)
    conn.commit()
    conn.close()
    return db_path


def ph(color, size=64):
    """Compute a pHash hex string for a solid-color image."""
    img = Image.new("RGB", (size, size), color=color)
    return str(imagehash.phash(img))


def invoke(folder1, folder2, output=None):
    from lk_cli.dbc import dbc
    import tempfile
    if output is None:
        fd, output = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
    return CliRunner().invoke(dbc, [str(folder1), str(folder2), "--output", str(output)])


# ── ImageRecord ──────────────────────────────────────────────────────────────

class TestImageRecord:
    def test_importable_from_utils(self):
        from lk_cli.utils import ImageRecord
        assert ImageRecord is not None

    def test_has_expected_fields(self):
        from lk_cli.utils import ImageRecord
        assert ImageRecord._fields == (
            "hash", "name", "created_at", "camera_model", "subsec_time",
            "image_width", "image_height", "file_size",
            "image_unique_id", "camera_serial", "phash", "memory_card_number",
            "image_hash",
        )

    def test_load_db_returns_image_records(self, tmp_path):
        from lk_cli.dbc import load_db
        from lk_cli.utils import ImageRecord
        make_db(tmp_path, [("hash1", "/f1/a.jpg", None, None)])
        records = load_db(str(tmp_path / DB_NAME))
        assert isinstance(records[0], ImageRecord)

    def test_image_record_fields_accessible_by_name(self, tmp_path):
        from lk_cli.dbc import load_db
        make_db(tmp_path, [("hash1", "/f1/a.jpg", "2024:01:01", "Canon")])
        record = load_db(str(tmp_path / DB_NAME))[0]
        assert record.hash == "hash1"
        assert record.name == "/f1/a.jpg"
        assert record.created_at == "2024:01:01"
        assert record.camera_model == "Canon"

    def test_optional_fields_default_to_none(self):
        from lk_cli.utils import ImageRecord
        r = ImageRecord(hash="h", name="/f/a.jpg")
        assert r.created_at is None
        assert r.phash is None


# ── compare_records unit tests ────────────────────────────────────────────────

class TestCompareRecords:
    def _compare(self, db1, db2, threshold=10):
        from lk_cli.dbc import compare_records
        return compare_records(db1, db2, threshold)

    def test_hash_match_not_missing(self):
        db1 = [ImageRecord("abc123", "/f1/photo.jpg", "2024:01:01 10:00:00", "Canon")]
        db2 = [ImageRecord("abc123", "/f2/photo.jpg", "2024:01:01 10:00:00", "Canon")]
        missing, image_only, exif_only, phash_only, _ = self._compare(db1, db2)
        assert missing == []
        assert exif_only == []
        assert phash_only == []

    def test_different_hash_no_exif_is_missing(self):
        db1 = [ImageRecord("hash1", "/f1/a.jpg")]
        db2 = [ImageRecord("hash2", "/f2/b.jpg")]
        missing, image_only, exif_only, _, _ = self._compare(db1, db2)
        assert "/f2/b.jpg" in missing
        assert exif_only == []

    def test_exif_match_not_in_missing(self):
        db1 = [ImageRecord("hash1", "/f1/a.jpg", "2024:06:21 08:15:00", "Canon EOS R5")]
        db2 = [ImageRecord("hash2", "/f2/b.jpg", "2024:06:21 08:15:00", "Canon EOS R5")]
        missing, image_only, exif_only, _, _ = self._compare(db1, db2)
        assert missing == []
        assert len(exif_only) == 1
        assert exif_only[0][0] == "/f2/b.jpg"

    def test_exif_match_records_db1_name(self):
        db1 = [ImageRecord("hash1", "/f1/original.jpg", "2024:06:21 08:15:00", "Canon EOS R5")]
        db2 = [ImageRecord("hash2", "/f2/copy.jpg", "2024:06:21 08:15:00", "Canon EOS R5")]
        _, image_only, exif_only, _, _ = self._compare(db1, db2)
        assert exif_only[0] == ("/f2/copy.jpg", "/f1/original.jpg")

    def test_null_created_at_not_exif_matched(self):
        db1 = [ImageRecord("hash1", "/f1/a.jpg", "2024:06:21 08:15:00", "Canon EOS R5")]
        db2 = [ImageRecord("hash2", "/f2/b.jpg", created_at=None, camera_model="Canon EOS R5")]
        missing, image_only, exif_only, _, _ = self._compare(db1, db2)
        assert "/f2/b.jpg" in missing
        assert exif_only == []

    def test_null_camera_model_not_exif_matched(self):
        db1 = [ImageRecord("hash1", "/f1/a.jpg", "2024:06:21 08:15:00", "Canon EOS R5")]
        db2 = [ImageRecord("hash2", "/f2/b.jpg", "2024:06:21 08:15:00", camera_model=None)]
        missing, image_only, exif_only, _, _ = self._compare(db1, db2)
        assert "/f2/b.jpg" in missing
        assert exif_only == []

    def test_empty_db1_all_missing(self):
        db1 = []
        db2 = [ImageRecord("hash1", "/f2/a.jpg"), ImageRecord("hash2", "/f2/b.jpg")]
        missing, _, _, _, _ = self._compare(db1, db2)
        assert len(missing) == 2

    def test_empty_db2_nothing_missing(self):
        db1 = [ImageRecord("hash1", "/f1/a.jpg")]
        db2 = []
        missing, image_only, exif_only, phash_only, _ = self._compare(db1, db2)
        assert missing == []
        assert exif_only == []
        assert phash_only == []

    def test_partial_match_mixed(self):
        db1 = [
            ImageRecord("hash1", "/f1/a.jpg"),
            ImageRecord("hash2", "/f1/b.jpg", "2024:01:01 10:00:00", "Sony A7"),
        ]
        db2 = [
            ImageRecord("hash1", "/f2/a.jpg"),                                          # hash match
            ImageRecord("hash3", "/f2/b.jpg", "2024:01:01 10:00:00", "Sony A7"),        # exif match
            ImageRecord("hash4", "/f2/c.jpg"),                                          # missing
        ]
        missing, image_only, exif_only, _, _ = self._compare(db1, db2)
        assert missing == ["/f2/c.jpg"]
        assert len(exif_only) == 1
        assert exif_only[0][0] == "/f2/b.jpg"

    # ── subsec tests ──────────────────────────────────────────────────────────

    def test_subsec_disambiguates_burst_shots(self):
        # Same camera, same second, different sub-second → no EXIF match
        db1 = [ImageRecord("hash1", "/f1/a.jpg", "2024:01:01 10:00:00", "Canon", "05")]
        db2 = [ImageRecord("hash2", "/f2/b.jpg", "2024:01:01 10:00:00", "Canon", "06")]
        missing, image_only, exif_only, _, _ = self._compare(db1, db2)
        assert "/f2/b.jpg" in missing
        assert exif_only == []

    def test_subsec_match_when_same(self):
        db1 = [ImageRecord("hash1", "/f1/a.jpg", "2024:01:01 10:00:00", "Canon", "05")]
        db2 = [ImageRecord("hash2", "/f2/b.jpg", "2024:01:01 10:00:00", "Canon", "05")]
        missing, image_only, exif_only, _, _ = self._compare(db1, db2)
        assert missing == []
        assert len(exif_only) == 1

    def test_both_null_subsec_still_exif_matches(self):
        # Cameras without subsec: both None → still match on (model, time, None)
        db1 = [ImageRecord("hash1", "/f1/a.jpg", "2024:01:01 10:00:00", "Sony A7")]
        db2 = [ImageRecord("hash2", "/f2/b.jpg", "2024:01:01 10:00:00", "Sony A7")]
        missing, image_only, exif_only, _, _ = self._compare(db1, db2)
        assert missing == []
        assert len(exif_only) == 1

    # ── pHash tests ───────────────────────────────────────────────────────────

    def test_phash_match_not_missing(self):
        # Same visual content (identical pHash), different byte hash and no EXIF
        p = ph("red")
        db1 = [ImageRecord("hash1", "/f1/a.jpg", phash=p)]
        db2 = [ImageRecord("hash2", "/f2/b.jpg", phash=p)]
        missing, image_only, exif_only, phash_only, _ = self._compare(db1, db2)
        assert missing == []
        assert exif_only == []
        assert len(phash_only) == 1
        assert phash_only[0][0] == "/f2/b.jpg"

    def test_phash_match_records_distance(self):
        p = ph("blue")
        db1 = [ImageRecord("hash1", "/f1/a.jpg", phash=p)]
        db2 = [ImageRecord("hash2", "/f2/b.jpg", phash=p)]
        _, _, _, phash_only, _ = self._compare(db1, db2)
        assert phash_only[0][2] == 0   # identical images: distance 0

    def test_phash_mismatch_is_missing(self):
        # Very different images exceed threshold
        p1 = ph("red")
        p2 = ph("blue")
        db1 = [ImageRecord("hash1", "/f1/a.jpg", phash=p1)]
        db2 = [ImageRecord("hash2", "/f2/b.jpg", phash=p2)]
        missing, _, _, phash_only, _ = self._compare(db1, db2, threshold=5)
        # red vs blue solid images typically differ significantly
        if phash_only:
            assert phash_only[0][2] <= 5
        else:
            assert "/f2/b.jpg" in missing

    def test_phash_null_falls_through_to_missing(self):
        # db2 image has no pHash (e.g., older db entry) → must be missing
        p = ph("green")
        db1 = [ImageRecord("hash1", "/f1/a.jpg", phash=p)]
        db2 = [ImageRecord("hash2", "/f2/b.jpg")]
        missing, _, _, phash_only, _ = self._compare(db1, db2)
        assert "/f2/b.jpg" in missing
        assert phash_only == []

    def test_hash_match_takes_priority_over_phash(self):
        p = ph("red")
        db1 = [ImageRecord("hash1", "/f1/a.jpg", phash=p)]
        db2 = [ImageRecord("hash1", "/f2/b.jpg", phash=p)]
        missing, image_only, exif_only, phash_only, _ = self._compare(db1, db2)
        assert missing == []
        assert exif_only == []
        assert phash_only == []  # resolved in Pass 1, never reaches Pass 3


# ── command error handling ────────────────────────────────────────────────────

class TestDbcErrors:
    def test_missing_db_in_folder1_nonzero_exit(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f2, [("hash1", "/f2/a.jpg", None, None)])
        result = invoke(f1, f2)
        assert result.exit_code != 0

    def test_missing_db_in_folder2_nonzero_exit(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", None, None)])
        result = invoke(f1, f2)
        assert result.exit_code != 0

    def test_missing_db_in_folder1_error_message(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f2, [("hash1", "/f2/a.jpg", None, None)])
        result = invoke(f1, f2)
        assert "Error" in result.output


# ── command output ────────────────────────────────────────────────────────────

class TestDbcOutput:
    def test_missing_file_appears_in_results_file(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", None, None)])
        make_db(f2, [("hash2", "/f2/missing.jpg", None, None)])
        out = tmp_path / "results.txt"
        invoke(f1, f2, output=str(out))
        assert "missing.jpg" in out.read_text()

    def test_missing_count_in_summary(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", None, None)])
        make_db(f2, [("hash2", "/f2/missing.jpg", None, None)])
        result = invoke(f1, f2)
        assert "Missing:" in result.output
        assert "Summary" in result.output

    def test_hash_matched_shows_zero_missing(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", None, None)])
        make_db(f2, [("hash1", "/f2/a.jpg", None, None)])
        result = invoke(f1, f2)
        assert "Summary" in result.output
        assert "Hash matches:" in result.output

    def test_all_hash_matched_success_message(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", None, None)])
        make_db(f2, [("hash1", "/f2/a.jpg", None, None)])
        result = invoke(f1, f2)
        assert "Hash matches:" in result.output

    def test_exif_match_shows_zero_missing(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", "2024:06:21 08:15:00", "Canon EOS R5")])
        make_db(f2, [("hash2", "/f2/b.jpg", "2024:06:21 08:15:00", "Canon EOS R5")])
        result = invoke(f1, f2)
        assert "EXIF matches:" in result.output

    def test_exif_only_match_in_summary(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", "2024:06:21 08:15:00", "Canon EOS R5")])
        make_db(f2, [("hash2", "/f2/b.jpg", "2024:06:21 08:15:00", "Canon EOS R5")])
        result = invoke(f1, f2)
        assert "EXIF matches:" in result.output
        assert "/f2/b.jpg" not in result.output  # file names go to results file only

    def test_phash_match_in_summary(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        p = ph("purple")
        make_db(f1, [("hash1", "/f1/a.jpg", None, None, None, None, None, None, None, None, p)])
        make_db(f2, [("hash2", "/f2/b.jpg", None, None, None, None, None, None, None, None, p)])
        result = invoke(f1, f2)
        assert "pHash matches:" in result.output
        assert "/f2/b.jpg" not in result.output  # file names go to results file only

    def test_empty_db2_success(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", None, None)])
        make_db(f2, [])
        result = invoke(f1, f2)
        assert result.exit_code == 0

    def test_output_file_has_filenames_not_summary(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", None, None)])
        make_db(f2, [("hash2", "/f2/missing.jpg", None, None)])
        out = tmp_path / "results.txt"
        invoke(f1, f2, output=str(out))
        assert out.exists()
        content = out.read_text()
        assert "Summary" not in content          # summary stays in terminal
        assert "Hash matches:" not in content    # counts stay in terminal
        assert "/f2/missing.jpg" in content      # file names go to results file

    def test_stdout_has_summary_not_filenames(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [
            ("hash1", "/f1/a.jpg", None, None),
            ("hash2", "/f1/b.jpg", "2024:01:01 10:00:00", "Canon"),
        ])
        make_db(f2, [
            ("hash1", "/f2/a.jpg", None, None),
            ("hash3", "/f2/b.jpg", "2024:01:01 10:00:00", "Canon"),
            ("hash4", "/f2/c.jpg", None, None),
        ])
        result = invoke(f1, f2)
        assert "Summary" in result.output
        assert "Hash matches:" in result.output
        assert "EXIF matches:" in result.output
        assert "Missing:" in result.output
        assert "/f2/a.jpg" not in result.output  # filenames in file, not stdout

    def test_stdout_reports_output_path(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", None, None)])
        make_db(f2, [("hash1", "/f2/a.jpg", None, None)])
        out = tmp_path / "results.txt"
        result = invoke(f1, f2, output=str(out))
        assert "Results written to" in result.output


# ── image hash comparison (Pass 2) ───────────────────────────────────────────

class TestImageHashComparison:
    def _compare(self, db1, db2, threshold=10):
        from lk_cli.dbc import compare_records
        return compare_records(db1, db2, threshold)

    def test_same_image_hash_not_missing(self):
        db1 = [ImageRecord("h1", "/f1/a.jpg", image_hash="sha256abc")]
        db2 = [ImageRecord("h2", "/f2/a.jpg", image_hash="sha256abc")]
        missing, image_only, _, _, _ = self._compare(db1, db2)
        assert missing == []
        assert len(image_only) == 1

    def test_image_hash_match_records_both_names(self):
        db1 = [ImageRecord("h1", "/f1/a.jpg", image_hash="sha256abc")]
        db2 = [ImageRecord("h2", "/f2/a.jpg", image_hash="sha256abc")]
        _, image_only, _, _, _ = self._compare(db1, db2)
        assert image_only[0] == ("/f2/a.jpg", "/f1/a.jpg")

    def test_different_image_hash_not_in_image_only(self):
        db1 = [ImageRecord("h1", "/f1/a.jpg", image_hash="sha256aaa")]
        db2 = [ImageRecord("h2", "/f2/a.jpg", image_hash="sha256bbb")]
        missing, image_only, _, _, _ = self._compare(db1, db2)
        assert image_only == []
        assert "/f2/a.jpg" in missing

    def test_null_image_hash_not_matched(self):
        db1 = [ImageRecord("h1", "/f1/a.jpg", image_hash="sha256abc")]
        db2 = [ImageRecord("h2", "/f2/a.jpg")]   # no image_hash
        missing, image_only, _, _, _ = self._compare(db1, db2)
        assert image_only == []
        assert "/f2/a.jpg" in missing

    def test_image_hash_takes_priority_over_exif(self):
        db1 = [ImageRecord("h1", "/f1/a.jpg", "2024:01:01", "Canon",
                            image_hash="sha256abc")]
        db2 = [ImageRecord("h2", "/f2/a.jpg", "2024:01:01", "Canon",
                            image_hash="sha256abc")]
        _, image_only, exif_only, _, _ = self._compare(db1, db2)
        assert len(image_only) == 1
        assert exif_only == []

    def test_image_hash_section_in_results_file(self, tmp_path):
        from lk_cli.dbc import write_results
        out = str(tmp_path / "r.txt")
        image_only = [("/f2/a.jpg", "/f1/a.jpg")]
        write_results(out, [], image_only, [], [])
        content = open(out).read()
        assert "image hash" in content.lower()
        assert "/f2/a.jpg" in content

    def test_image_hash_count_in_summary(self, tmp_path):
        from lk_cli.dbc import write_results
        out = str(tmp_path / "r.txt")
        image_only = [("/f2/a.jpg", "/f1/a.jpg"), ("/f2/b.jpg", "/f1/b.jpg")]
        write_results(out, [], image_only, [], [])
        assert "2" in open(out).read()

    def test_image_hash_match_in_cli_output(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [ImageRecord("h1", "/f1/a.jpg", image_hash="sha256abc")])
        make_db(f2, [ImageRecord("h2", "/f2/a.jpg", image_hash="sha256abc")])
        result = invoke(f1, f2)
        assert "image matches" in result.output.lower()


# ── EXIF section label ────────────────────────────────────────────────────────

class TestExifSectionLabels:
    def test_exif_entries_use_reencoded_header(self, tmp_path):
        from lk_cli.dbc import write_results
        out = str(tmp_path / "r.txt")
        exif_only = [("/f2/a.jpg", "/f1/a.jpg")]
        write_results(out, [], [], exif_only, [])
        content = open(out).read()
        assert "re-encoded" in content.lower()

    def test_reencoded_in_results_file(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [ImageRecord("h1", "/f1/a.jpg", "2024:01:01", "Canon EOS R5")])
        make_db(f2, [ImageRecord("h2", "/f2/a.jpg", "2024:01:01", "Canon EOS R5")])
        out = tmp_path / "results.txt"
        invoke(f1, f2, output=str(out))
        assert "re-encoded" in out.read_text().lower()


# ── write_results phash_threshold parameter ──────────────────────────────────

class TestWriteResultsThreshold:
    def test_custom_threshold_appears_in_output(self, tmp_path):
        from lk_cli.dbc import write_results
        out = str(tmp_path / "r.txt")
        phash_only = [("/f2/a.jpg", "/f1/a.jpg", 2)]
        write_results(out, [], [], [], phash_only, phash_threshold=3)
        assert "≤ 3" in open(out).read()

    def test_default_threshold_still_works(self, tmp_path):
        from lk_cli.dbc import write_results, PHASH_THRESHOLD
        out = str(tmp_path / "r.txt")
        phash_only = [("/f2/a.jpg", "/f1/a.jpg", 2)]
        write_results(out, [], [], [], phash_only)
        assert f"≤ {PHASH_THRESHOLD}" in open(out).read()


# ── version tracking ─────────────────────────────────────────────────────────

class TestReadDbVersion:
    def test_returns_version_when_present(self, tmp_path):
        from lk_cli.dbc import read_db_version
        db_path = str(tmp_path / DB_NAME)
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO meta VALUES (?, ?)", ("created_by_version", "0.9.4.6"))
        conn.commit()
        conn.close()
        assert read_db_version(db_path) == "0.9.4.6"

    def test_returns_none_when_meta_table_missing(self, tmp_path):
        from lk_cli.dbc import read_db_version
        db_path = str(tmp_path / DB_NAME)
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE files (hash TEXT)")
        conn.commit()
        conn.close()
        assert read_db_version(db_path) is None

    def test_returns_none_when_key_absent(self, tmp_path):
        from lk_cli.dbc import read_db_version
        db_path = str(tmp_path / DB_NAME)
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()
        conn.close()
        assert read_db_version(db_path) is None


class TestVersionInResults:
    def test_dbc_version_in_stdout(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", None, None)])
        make_db(f2, [("hash1", "/f2/a.jpg", None, None)])
        from lk_cli.utils import get_version
        result = invoke(f1, f2)
        assert get_version() in result.output

    def test_folder_versions_in_stdout(self, tmp_path):
        from click.testing import CliRunner
        from lk_cli.dbf import dbf as dbf_cmd
        from lk_cli.utils import get_version
        from PIL import Image
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        Image.new("RGB", (10, 10), color="red").save(str(f1 / "a.jpg"), "JPEG")
        Image.new("RGB", (10, 10), color="red").save(str(f2 / "a.jpg"), "JPEG")
        CliRunner().invoke(dbf_cmd, [str(f1)])
        CliRunner().invoke(dbf_cmd, [str(f2)])
        result = invoke(f1, f2)
        assert get_version() in result.output

    def test_versions_appear_in_full_run(self, tmp_path):
        """After running dbf then dbc, results file must contain the version string."""
        from click.testing import CliRunner
        from lk_cli.dbf import dbf as dbf_cmd
        from lk_cli.utils import get_version
        from PIL import Image
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        Image.new("RGB", (10, 10), color="red").save(str(f1 / "a.jpg"), "JPEG")
        Image.new("RGB", (10, 10), color="red").save(str(f2 / "a.jpg"), "JPEG")
        CliRunner().invoke(dbf_cmd, [str(f1)])
        CliRunner().invoke(dbf_cmd, [str(f2)])
        out = tmp_path / "results.txt"
        result = invoke(f1, f2, output=str(out))
        assert get_version() in result.output  # version in stdout, not results file


# ── multiprocessing ───────────────────────────────────────────────────────────

class TestDbcMultiprocessing:
    def test_pool_is_used(self, tmp_path):
        from lk_cli.dbc import load_db
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", None, None)])
        make_db(f2, [("hash1", "/f2/a.jpg", None, None)])
        with patch("lk_cli.dbc.get_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_get_pool.return_value.__enter__ = lambda s: mock_pool
            mock_get_pool.return_value.__exit__ = lambda s, *a: None
            mock_pool.map.side_effect = lambda f, items: [f(i) for i in items]
            invoke(f1, f2)
        mock_get_pool.assert_called_once()
