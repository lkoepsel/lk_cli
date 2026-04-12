import os
import multiprocessing.pool
import pytest
import xxhash
from unittest.mock import patch
import importlib
from lk_cli.utils import hash_folder_mp, process_file, hash_hashes, calculate_file_hash, hash_file, BLOCKSIZE
import lk_cli.utils as utils_module


def make_file(directory, name, content=b"hello"):
    path = os.path.join(directory, name)
    with open(path, "wb") as f:
        f.write(content)
    return path


def xxhash_of(content):
    h = xxhash.xxh64()
    h.update(content)
    return h.hexdigest()


class TestProcessFile:
    def test_returns_hash_and_relpath(self, tmp_path):
        filepath = make_file(str(tmp_path), "a.txt", b"data")
        result = process_file(str(tmp_path), filepath)
        assert result == (xxhash_of(b"data"), "a.txt")

    def test_broken_symlink_returns_none(self, tmp_path, capsys):
        link = os.path.join(str(tmp_path), "dead.lnk")
        os.symlink("/nonexistent", link)
        assert process_file(str(tmp_path), link) is None
        assert "broken symlink" in capsys.readouterr().out.lower()

    def test_missing_file_returns_none(self, tmp_path, capsys):
        ghost = os.path.join(str(tmp_path), "ghost.txt")
        assert process_file(str(tmp_path), ghost) is None
        assert "warning" in capsys.readouterr().out.lower()

    def test_relpath_for_nested_file(self, tmp_path):
        sub = os.path.join(str(tmp_path), "sub")
        os.makedirs(sub)
        filepath = make_file(sub, "b.txt", b"y")
        _, relpath = process_file(str(tmp_path), filepath)
        assert relpath == os.path.join("sub", "b.txt")

    def test_returns_none_when_hash_fails(self, tmp_path):
        filepath = make_file(str(tmp_path), "f.txt", b"x")
        with patch("lk_cli.utils.hash_file", return_value=None):
            assert process_file(str(tmp_path), filepath) is None


class TestHashFolderMpSingleDispatch:
    def test_pool_map_called_exactly_once(self, tmp_path):
        for i in range(3):
            sub = os.path.join(str(tmp_path), f"sub{i}")
            os.makedirs(sub)
            make_file(sub, "a.txt", f"a{i}".encode())
            make_file(sub, "b.txt", f"b{i}".encode())

        call_count = []
        original_map = multiprocessing.pool.Pool.map

        def counting_map(self, func, iterable, *args, **kwargs):
            call_count.append(1)
            return original_map(self, func, iterable, *args, **kwargs)

        with patch.object(multiprocessing.pool.Pool, "map", counting_map):
            hash_folder_mp(str(tmp_path))

        assert len(call_count) == 1, (
            f"pool.map called {len(call_count)} times; expected 1"
        )

    def test_correct_hashes_flat(self, tmp_path):
        make_file(str(tmp_path), "x.txt", b"aaa")
        make_file(str(tmp_path), "y.txt", b"bbb")
        hashes, folder_hash, *_ = hash_folder_mp(str(tmp_path))
        assert xxhash_of(b"aaa") in hashes
        assert xxhash_of(b"bbb") in hashes
        assert isinstance(folder_hash, str)

    def test_correct_hashes_nested(self, tmp_path):
        sub = os.path.join(str(tmp_path), "nested")
        os.makedirs(sub)
        make_file(str(tmp_path), "root.txt", b"r")
        make_file(sub, "child.txt", b"c")
        hashes, *_ = hash_folder_mp(str(tmp_path))
        assert xxhash_of(b"r") in hashes
        assert xxhash_of(b"c") in hashes

    def test_return_type(self, tmp_path):
        make_file(str(tmp_path), "t.txt", b"t")
        result = hash_folder_mp(str(tmp_path))
        assert isinstance(result, tuple) and len(result) == 3
        assert isinstance(result[0], dict) and isinstance(result[1], str)

    def test_deterministic_folder_hash(self, tmp_path):
        make_file(str(tmp_path), "f.txt", b"same")
        _, hash1, *_ = hash_folder_mp(str(tmp_path))
        _, hash2, *_ = hash_folder_mp(str(tmp_path))
        assert hash1 == hash2


class TestEdgeCases:
    def test_empty_dir_returns_empty_dict(self, tmp_path):
        hashes, folder_hash, *_ = hash_folder_mp(str(tmp_path))
        assert hashes == {}
        assert isinstance(folder_hash, str)

    def test_no_pool_spawned_for_empty_dir(self, tmp_path):
        with patch("lk_cli.utils.Pool") as mock_pool:
            hash_folder_mp(str(tmp_path))
            mock_pool.assert_not_called()

    def test_no_pool_spawned_when_only_dotfiles(self, tmp_path):
        make_file(str(tmp_path), ".DS_Store", b"junk")
        with patch("lk_cli.utils.Pool") as mock_pool:
            hash_folder_mp(str(tmp_path))
            mock_pool.assert_not_called()

    def test_dotfiles_excluded(self, tmp_path):
        make_file(str(tmp_path), ".hidden", b"secret")
        make_file(str(tmp_path), "visible.txt", b"public")
        hashes, *_ = hash_folder_mp(str(tmp_path))
        assert len(hashes) == 1
        assert xxhash_of(b"public") in hashes

    def test_broken_symlink_skipped_real_file_included(self, tmp_path, capsys):
        os.symlink("/no/target", os.path.join(str(tmp_path), "broken.lnk"))
        make_file(str(tmp_path), "real.txt", b"real")
        hashes, *_ = hash_folder_mp(str(tmp_path))
        assert xxhash_of(b"real") in hashes

    def test_hash_collision_one_entry(self, tmp_path):
        # Two files with identical content — dict has one entry; documented behaviour
        make_file(str(tmp_path), "a.txt", b"same")
        make_file(str(tmp_path), "b.txt", b"same")
        hashes, *_ = hash_folder_mp(str(tmp_path))
        assert len(hashes) == 1
        assert hashes[xxhash_of(b"same")] in ("a.txt", "b.txt")

    def test_only_subdirectories_no_files(self, tmp_path):
        os.makedirs(os.path.join(str(tmp_path), "empty_sub"))
        hashes, *_ = hash_folder_mp(str(tmp_path))
        assert hashes == {}


class TestHashHashes:
    def test_empty_dict_returns_string(self):
        result = hash_hashes({})
        assert isinstance(result, str) and len(result) > 0

    def test_same_dict_produces_same_hash(self):
        d = {"abc123": "some/path.txt", "def456": "other.txt"}
        assert hash_hashes(d) == hash_hashes(d)


class TestCalculateFileHash:
    def test_default_chunk_size_equals_blocksize(self):
        import inspect
        sig = inspect.signature(calculate_file_hash)
        assert sig.parameters["chunk_size"].default == BLOCKSIZE

    def test_large_file_read_count(self, tmp_path):
        # File is 2*BLOCKSIZE + 100 bytes → exactly 3 reads at BLOCKSIZE, many more at 8KB
        content = b"x" * (2 * BLOCKSIZE + 100)
        filepath = make_file(str(tmp_path), "large.bin", content)

        read_calls = []
        real_open = open

        def tracking_open(path, mode="r", *args, **kwargs):
            fh = real_open(path, mode, *args, **kwargs)
            if path == filepath:
                orig_read = fh.read

                def counting_read(n=-1):
                    chunk = orig_read(n)
                    if chunk:
                        read_calls.append(len(chunk))
                    return chunk

                fh.read = counting_read
            return fh

        with patch("builtins.open", tracking_open):
            calculate_file_hash(filepath)

        assert len(read_calls) == 3, (
            f"Expected 3 reads at BLOCKSIZE; got {len(read_calls)}"
        )

    def test_produces_correct_hash(self, tmp_path):
        content = b"hello world"
        filepath = make_file(str(tmp_path), "f.txt", content)
        expected = xxhash_of(content)
        assert calculate_file_hash(filepath) == expected

    def test_matches_hash_file(self, tmp_path):
        content = b"consistency check"
        filepath = make_file(str(tmp_path), "c.txt", content)
        assert calculate_file_hash(filepath) == hash_file(filepath)

    def test_small_file_hash(self, tmp_path):
        # File smaller than both 8KB and BLOCKSIZE
        content = b"tiny"
        filepath = make_file(str(tmp_path), "small.txt", content)
        assert calculate_file_hash(filepath) == xxhash_of(content)

    def test_empty_file_hash(self, tmp_path):
        filepath = make_file(str(tmp_path), "empty.txt", b"")
        result = calculate_file_hash(filepath)
        assert isinstance(result, str) and len(result) > 0


class TestCores:
    def test_cores_uses_cpu_count(self):
        with patch("os.cpu_count", return_value=42):
            importlib.reload(utils_module)
        try:
            assert utils_module.CORES == 42
        finally:
            importlib.reload(utils_module)  # restore original state

    def test_cores_fallback_when_cpu_count_none(self):
        with patch("os.cpu_count", return_value=None):
            importlib.reload(utils_module)
        try:
            assert utils_module.CORES == 8
        finally:
            importlib.reload(utils_module)


class TestCreateDbSchema:
    def test_importable_from_utils(self):
        from lk_cli.utils import create_db_schema
        assert callable(create_db_schema)

    def test_creates_meta_table(self, tmp_path):
        import sqlite3
        from lk_cli.utils import create_db_schema
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        create_db_schema(conn)
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        conn.close()
        assert "meta" in tables

    def test_meta_table_has_key_value_columns(self, tmp_path):
        import sqlite3
        from lk_cli.utils import create_db_schema
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        create_db_schema(conn)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(meta)")}
        conn.close()
        assert cols == {"key", "value"}

    def test_drops_existing_meta_table(self, tmp_path):
        import sqlite3
        from lk_cli.utils import create_db_schema
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.execute("CREATE TABLE meta (old_col TEXT)")
        create_db_schema(conn)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(meta)")}
        conn.close()
        assert "key" in cols
        assert "old_col" not in cols

    def test_creates_files_table(self, tmp_path):
        import sqlite3
        from lk_cli.utils import create_db_schema
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        create_db_schema(conn)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(files)")}
        conn.close()
        assert cols == {
            "hash", "name", "created_at", "camera_model", "subsec_time",
            "image_width", "image_height", "file_size",
            "image_unique_id", "camera_serial", "phash", "memory_card_number",
            "image_hash",
        }

    def test_columns_match_image_record_fields(self, tmp_path):
        import sqlite3
        from lk_cli.utils import create_db_schema, ImageRecord
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        create_db_schema(conn)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(files)")}
        conn.close()
        assert cols == set(ImageRecord._fields)

    def test_drops_existing_table(self, tmp_path):
        import sqlite3
        from lk_cli.utils import create_db_schema
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.execute("CREATE TABLE files (old_col TEXT)")
        create_db_schema(conn)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(files)")}
        conn.close()
        assert "old_col" not in cols
        assert "hash" in cols

    def test_dbf_uses_create_db_schema(self, tmp_path):
        """dbf command must call create_db_schema rather than inline CREATE TABLE."""
        from lk_cli.utils import create_db_schema
        from unittest.mock import patch, call
        import lk_cli.dbf as dbf_mod
        assert hasattr(dbf_mod, "create_db_schema"), (
            "dbf.py must import create_db_schema from utils"
        )


class TestDbName:
    def test_db_name_importable_from_utils(self):
        from lk_cli.utils import DB_NAME
        assert DB_NAME == ".dbf.db"

    def test_dbf_uses_db_name_from_utils(self):
        import lk_cli.dbf as dbf_mod
        from lk_cli.utils import DB_NAME
        assert dbf_mod.DB_NAME == DB_NAME

    def test_dbc_uses_db_name_from_utils(self):
        import lk_cli.dbc as dbc_mod
        from lk_cli.utils import DB_NAME
        assert dbc_mod.DB_NAME == DB_NAME


class TestSharedPool:
    def test_get_pool_exists(self):
        from lk_cli.utils import get_pool  # ImportError if missing
        assert callable(get_pool)

    def test_get_pool_is_context_manager(self):
        from lk_cli.utils import get_pool
        with get_pool() as pool:
            assert pool is not None

    def test_hash_folder_mp_accepts_pool_param(self, tmp_path):
        make_file(str(tmp_path), "f.txt", b"data")
        from lk_cli.utils import get_pool
        with get_pool() as pool:
            result = hash_folder_mp(str(tmp_path), pool=pool)
        assert isinstance(result, tuple)

    def test_pool_not_constructed_when_passed(self, tmp_path):
        make_file(str(tmp_path), "f.txt", b"data")
        from multiprocessing import Pool as RealPool
        with RealPool(2) as real_pool:
            with patch("lk_cli.utils.Pool") as mock_pool_cls:
                hash_folder_mp(str(tmp_path), pool=real_pool)
            mock_pool_cls.assert_not_called()

    def test_results_correct_with_shared_pool(self, tmp_path):
        make_file(str(tmp_path), "a.txt", b"aaa")
        make_file(str(tmp_path), "b.txt", b"bbb")
        from lk_cli.utils import get_pool
        with get_pool() as pool:
            hashes, folder_hash, *_ = hash_folder_mp(str(tmp_path), pool=pool)
        assert xxhash_of(b"aaa") in hashes
        assert xxhash_of(b"bbb") in hashes

    def test_hash_folder_mp_default_still_works(self, tmp_path):
        make_file(str(tmp_path), "x.txt", b"x")
        hashes, folder_hash, *_ = hash_folder_mp(str(tmp_path))
        assert xxhash_of(b"x") in hashes


# ── Issue #5: last_modified tracked during walk ───────────────────────────────

class TestLastModifiedInResult:
    def test_return_tuple_has_last_modified(self, tmp_path):
        make_file(str(tmp_path), "f.txt", b"data")
        result = hash_folder_mp(str(tmp_path))
        assert len(result) == 3
        last_mod = result[2]
        assert isinstance(last_mod, list) and len(last_mod) == 2

    def test_last_modified_identifies_newest(self, tmp_path):
        older = make_file(str(tmp_path), "older.txt", b"old")
        newer = make_file(str(tmp_path), "newer.txt", b"new")
        os.utime(older, (1_000_000, 1_000_000))
        os.utime(newer, (2_000_000, 2_000_000))
        _, _, last_mod = hash_folder_mp(str(tmp_path))
        assert last_mod[0] == 2_000_000.0
        assert last_mod[1] == newer

    def test_last_modified_none_for_empty_dir(self, tmp_path):
        _, _, last_mod = hash_folder_mp(str(tmp_path))
        assert last_mod == [0, None]


# ── Issue #6: parallel hashing in dedup ──────────────────────────────────────

class TestHashFilesForDedup:
    def test_groups_duplicates_by_hash(self, tmp_path):
        from lk_cli.utils import hash_files_for_dedup
        make_file(str(tmp_path), "a.txt", b"same")
        make_file(str(tmp_path), "b.txt", b"same")
        make_file(str(tmp_path), "c.txt", b"different")
        result = hash_files_for_dedup(str(tmp_path))
        h_same = xxhash_of(b"same")
        h_diff = xxhash_of(b"different")
        assert len(result[h_same]) == 2
        assert len(result[h_diff]) == 1

    def test_excludes_dotfiles(self, tmp_path):
        from lk_cli.utils import hash_files_for_dedup
        make_file(str(tmp_path), ".hidden", b"secret")
        make_file(str(tmp_path), "visible.txt", b"public")
        result = hash_files_for_dedup(str(tmp_path))
        all_paths = [p for paths in result.values() for p in paths]
        assert not any(os.path.basename(p).startswith(".") for p in all_paths)

    def test_uses_pool_for_hashing(self, tmp_path):
        from lk_cli.utils import hash_files_for_dedup
        make_file(str(tmp_path), "f.txt", b"data")
        with patch("lk_cli.utils.Pool") as mock_pool_cls:
            mock_pool_cls.return_value.__enter__ = lambda s: s
            mock_pool_cls.return_value.__exit__ = lambda s, *a: None
            mock_pool_cls.return_value.map = lambda f, items: [hash_file(i) for i in items]
            hash_files_for_dedup(str(tmp_path))
        mock_pool_cls.assert_called_once()

    def test_returns_empty_for_empty_dir(self, tmp_path):
        from lk_cli.utils import hash_files_for_dedup
        result = hash_files_for_dedup(str(tmp_path))
        assert len(result) == 0


# ── Issue #7: hc.py correctness bug ──────────────────────────────────────────

class TestHcBugFix:
    def test_hc_detects_path_mismatch(self, tmp_path):
        from click.testing import CliRunner
        from lk_cli.hc import hc
        from lk_cli.utils import write_json
        folder1 = os.path.join(str(tmp_path), "f1")
        folder2 = os.path.join(str(tmp_path), "f2")
        os.makedirs(folder1)
        os.makedirs(folder2)
        h = xxhash_of(b"same content")
        # Same content, different relative paths — hc should detect mismatch
        write_json(folder1, ".hashes.json", {h: "a.txt"})
        write_json(folder2, ".hashes.json", {h: "b.txt"})
        result = CliRunner().invoke(hc, [folder1, folder2])
        assert "does not match" in result.output

    def test_hc_no_keyerror_when_files_match(self, tmp_path):
        from click.testing import CliRunner
        from lk_cli.hc import hc
        from lk_cli.utils import write_json
        folder1 = os.path.join(str(tmp_path), "f1")
        folder2 = os.path.join(str(tmp_path), "f2")
        os.makedirs(folder1)
        os.makedirs(folder2)
        h = xxhash_of(b"same content")
        # Same content, same relative path — should match cleanly, no KeyError
        write_json(folder1, ".hashes.json", {h: "a.txt"})
        write_json(folder2, ".hashes.json", {h: "a.txt"})
        result = CliRunner().invoke(hc, [folder1, folder2])
        assert "KeyError" not in result.output
        assert "does not match" not in result.output
