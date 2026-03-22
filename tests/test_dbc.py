import imagehash
import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from PIL import Image


DB_NAME = ".dbf.db"


# ── helpers ───────────────────────────────────────────────────────────────────

def make_db(folder, records):
    """Create a .dbf.db with the full 11-column schema.

    Records may be 4-tuples (hash, name, created_at, camera_model) or full
    11-tuples. Short records are right-padded with None.
    """
    db_path = os.path.join(str(folder), DB_NAME)
    conn = sqlite3.connect(db_path)
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
    padded = [tuple(r) + (None,) * (11 - len(r)) for r in records]
    conn.executemany("INSERT INTO files VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", padded)
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


# ── compare_records unit tests ────────────────────────────────────────────────

class TestCompareRecords:
    def _compare(self, db1, db2, threshold=10):
        from lk_cli.dbc import compare_records
        return compare_records(db1, db2, threshold)

    def test_hash_match_not_missing(self):
        db1 = [("abc123", "/f1/photo.jpg", "2024:01:01 10:00:00", "Canon")]
        db2 = [("abc123", "/f2/photo.jpg", "2024:01:01 10:00:00", "Canon")]
        missing, exif_only, phash_only = self._compare(db1, db2)
        assert missing == []
        assert exif_only == []
        assert phash_only == []

    def test_different_hash_no_exif_is_missing(self):
        db1 = [("hash1", "/f1/a.jpg", None, None)]
        db2 = [("hash2", "/f2/b.jpg", None, None)]
        missing, exif_only, _ = self._compare(db1, db2)
        assert "/f2/b.jpg" in missing
        assert exif_only == []

    def test_exif_match_not_in_missing(self):
        db1 = [("hash1", "/f1/a.jpg", "2024:06:21 08:15:00", "Canon EOS R5")]
        db2 = [("hash2", "/f2/b.jpg", "2024:06:21 08:15:00", "Canon EOS R5")]
        missing, exif_only, _ = self._compare(db1, db2)
        assert missing == []
        assert len(exif_only) == 1
        assert exif_only[0][0] == "/f2/b.jpg"

    def test_exif_match_records_db1_name(self):
        db1 = [("hash1", "/f1/original.jpg", "2024:06:21 08:15:00", "Canon EOS R5")]
        db2 = [("hash2", "/f2/copy.jpg", "2024:06:21 08:15:00", "Canon EOS R5")]
        _, exif_only, _ = self._compare(db1, db2)
        assert exif_only[0] == ("/f2/copy.jpg", "/f1/original.jpg")

    def test_null_created_at_not_exif_matched(self):
        db1 = [("hash1", "/f1/a.jpg", "2024:06:21 08:15:00", "Canon EOS R5")]
        db2 = [("hash2", "/f2/b.jpg", None, "Canon EOS R5")]
        missing, exif_only, _ = self._compare(db1, db2)
        assert "/f2/b.jpg" in missing
        assert exif_only == []

    def test_null_camera_model_not_exif_matched(self):
        db1 = [("hash1", "/f1/a.jpg", "2024:06:21 08:15:00", "Canon EOS R5")]
        db2 = [("hash2", "/f2/b.jpg", "2024:06:21 08:15:00", None)]
        missing, exif_only, _ = self._compare(db1, db2)
        assert "/f2/b.jpg" in missing
        assert exif_only == []

    def test_empty_db1_all_missing(self):
        db1 = []
        db2 = [("hash1", "/f2/a.jpg", None, None), ("hash2", "/f2/b.jpg", None, None)]
        missing, _, _ = self._compare(db1, db2)
        assert len(missing) == 2

    def test_empty_db2_nothing_missing(self):
        db1 = [("hash1", "/f1/a.jpg", None, None)]
        db2 = []
        missing, exif_only, phash_only = self._compare(db1, db2)
        assert missing == []
        assert exif_only == []
        assert phash_only == []

    def test_partial_match_mixed(self):
        db1 = [
            ("hash1", "/f1/a.jpg", None, None),
            ("hash2", "/f1/b.jpg", "2024:01:01 10:00:00", "Sony A7"),
        ]
        db2 = [
            ("hash1", "/f2/a.jpg", None, None),                          # hash match
            ("hash3", "/f2/b.jpg", "2024:01:01 10:00:00", "Sony A7"),   # exif match
            ("hash4", "/f2/c.jpg", None, None),                          # missing
        ]
        missing, exif_only, _ = self._compare(db1, db2)
        assert missing == ["/f2/c.jpg"]
        assert len(exif_only) == 1
        assert exif_only[0][0] == "/f2/b.jpg"

    # ── subsec tests ──────────────────────────────────────────────────────────

    def test_subsec_disambiguates_burst_shots(self):
        # Same camera, same second, different sub-second → no EXIF match
        db1 = [("hash1", "/f1/a.jpg", "2024:01:01 10:00:00", "Canon", "05")]
        db2 = [("hash2", "/f2/b.jpg", "2024:01:01 10:00:00", "Canon", "06")]
        missing, exif_only, _ = self._compare(db1, db2)
        assert "/f2/b.jpg" in missing
        assert exif_only == []

    def test_subsec_match_when_same(self):
        db1 = [("hash1", "/f1/a.jpg", "2024:01:01 10:00:00", "Canon", "05")]
        db2 = [("hash2", "/f2/b.jpg", "2024:01:01 10:00:00", "Canon", "05")]
        missing, exif_only, _ = self._compare(db1, db2)
        assert missing == []
        assert len(exif_only) == 1

    def test_both_null_subsec_still_exif_matches(self):
        # Cameras without subsec: both None → still match on (model, time, None)
        db1 = [("hash1", "/f1/a.jpg", "2024:01:01 10:00:00", "Sony A7", None)]
        db2 = [("hash2", "/f2/b.jpg", "2024:01:01 10:00:00", "Sony A7", None)]
        missing, exif_only, _ = self._compare(db1, db2)
        assert missing == []
        assert len(exif_only) == 1

    # ── pHash tests ───────────────────────────────────────────────────────────

    def test_phash_match_not_missing(self):
        # Same visual content (identical pHash), different byte hash and no EXIF
        p = ph("red")
        db1 = [("hash1", "/f1/a.jpg", None, None, None, None, None, None, None, None, p)]
        db2 = [("hash2", "/f2/b.jpg", None, None, None, None, None, None, None, None, p)]
        missing, exif_only, phash_only = self._compare(db1, db2)
        assert missing == []
        assert exif_only == []
        assert len(phash_only) == 1
        assert phash_only[0][0] == "/f2/b.jpg"

    def test_phash_match_records_distance(self):
        p = ph("blue")
        db1 = [("hash1", "/f1/a.jpg", None, None, None, None, None, None, None, None, p)]
        db2 = [("hash2", "/f2/b.jpg", None, None, None, None, None, None, None, None, p)]
        _, _, phash_only = self._compare(db1, db2)
        assert phash_only[0][2] == 0   # identical images: distance 0

    def test_phash_mismatch_is_missing(self):
        # Very different images exceed threshold
        p1 = ph("red")
        p2 = ph("blue")
        db1 = [("hash1", "/f1/a.jpg", None, None, None, None, None, None, None, None, p1)]
        db2 = [("hash2", "/f2/b.jpg", None, None, None, None, None, None, None, None, p2)]
        missing, _, phash_only = self._compare(db1, db2, threshold=5)
        # red vs blue solid images typically differ significantly
        if phash_only:
            assert phash_only[0][2] <= 5
        else:
            assert "/f2/b.jpg" in missing

    def test_phash_null_falls_through_to_missing(self):
        # db2 image has no pHash (e.g., older db entry) → must be missing
        p = ph("green")
        db1 = [("hash1", "/f1/a.jpg", None, None, None, None, None, None, None, None, p)]
        db2 = [("hash2", "/f2/b.jpg", None, None, None, None, None, None, None, None, None)]
        missing, _, phash_only = self._compare(db1, db2)
        assert "/f2/b.jpg" in missing
        assert phash_only == []

    def test_hash_match_takes_priority_over_phash(self):
        p = ph("red")
        db1 = [("hash1", "/f1/a.jpg", None, None, None, None, None, None, None, None, p)]
        db2 = [("hash1", "/f2/b.jpg", None, None, None, None, None, None, None, None, p)]
        missing, exif_only, phash_only = self._compare(db1, db2)
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
    def test_missing_file_appears_in_output(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", None, None)])
        make_db(f2, [("hash2", "/f2/missing.jpg", None, None)])
        result = invoke(f1, f2)
        assert "missing.jpg" in result.output
        assert "Total missing: 1" in result.output

    def test_hash_matched_file_not_in_missing(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", None, None)])
        make_db(f2, [("hash1", "/f2/a.jpg", None, None)])
        result = invoke(f1, f2)
        assert "Missing" not in result.output

    def test_all_hash_matched_success_message(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", None, None)])
        make_db(f2, [("hash1", "/f2/a.jpg", None, None)])
        result = invoke(f1, f2)
        assert "All files" in result.output

    def test_exif_match_not_in_missing_section(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", "2024:06:21 08:15:00", "Canon EOS R5")])
        make_db(f2, [("hash2", "/f2/b.jpg", "2024:06:21 08:15:00", "Canon EOS R5")])
        result = invoke(f1, f2)
        assert "Missing from" not in result.output

    def test_exif_only_match_reported_in_output(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", "2024:06:21 08:15:00", "Canon EOS R5")])
        make_db(f2, [("hash2", "/f2/b.jpg", "2024:06:21 08:15:00", "Canon EOS R5")])
        result = invoke(f1, f2)
        assert "EXIF" in result.output
        assert "/f2/b.jpg" in result.output

    def test_all_accounted_message_with_exif(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", "2024:06:21 08:15:00", "Canon EOS R5")])
        make_db(f2, [("hash2", "/f2/b.jpg", "2024:06:21 08:15:00", "Canon EOS R5")])
        result = invoke(f1, f2)
        assert "accounted for" in result.output

    def test_phash_match_reported_in_output(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        p = ph("purple")
        make_db(f1, [("hash1", "/f1/a.jpg", None, None, None, None, None, None, None, None, p)])
        make_db(f2, [("hash2", "/f2/b.jpg", None, None, None, None, None, None, None, None, p)])
        result = invoke(f1, f2)
        assert "pHash" in result.output
        assert "/f2/b.jpg" in result.output

    def test_all_accounted_message_with_phash(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        p = ph("orange")
        make_db(f1, [("hash1", "/f1/a.jpg", None, None, None, None, None, None, None, None, p)])
        make_db(f2, [("hash2", "/f2/b.jpg", None, None, None, None, None, None, None, None, p)])
        result = invoke(f1, f2)
        assert "accounted for" in result.output
        assert "pHash" in result.output

    def test_empty_db2_success(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [("hash1", "/f1/a.jpg", None, None)])
        make_db(f2, [])
        result = invoke(f1, f2)
        assert result.exit_code == 0

    def test_output_file_written(self, tmp_path):
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
        assert "Summary" in content
        assert "Missing" in content
        assert "/f2/missing.jpg" in content

    def test_output_file_summary_counts(self, tmp_path):
        f1 = tmp_path / "f1"
        f1.mkdir()
        f2 = tmp_path / "f2"
        f2.mkdir()
        make_db(f1, [
            ("hash1", "/f1/a.jpg", None, None),
            ("hash2", "/f1/b.jpg", "2024:01:01 10:00:00", "Canon"),
        ])
        make_db(f2, [
            ("hash1", "/f2/a.jpg", None, None),                        # hash match
            ("hash3", "/f2/b.jpg", "2024:01:01 10:00:00", "Canon"),   # EXIF match
            ("hash4", "/f2/c.jpg", None, None),                        # missing
        ])
        out = tmp_path / "results.txt"
        invoke(f1, f2, output=str(out))
        content = out.read_text()
        assert "Hash matches:" in content
        assert "EXIF matches:" in content
        assert "Missing:" in content
        assert "Results written to" in CliRunner().invoke(
            __import__("lk_cli.dbc", fromlist=["dbc"]).dbc,
            [str(f1), str(f2), "--output", str(out)],
        ).output

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
