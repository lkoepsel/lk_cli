import os
import multiprocessing.pool
import pytest
import xxhash
from unittest.mock import patch
from lk_cli.utils import hash_folder_mp, process_file, hash_hashes


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
        hashes, folder_hash = hash_folder_mp(str(tmp_path))
        assert xxhash_of(b"aaa") in hashes
        assert xxhash_of(b"bbb") in hashes
        assert isinstance(folder_hash, str)

    def test_correct_hashes_nested(self, tmp_path):
        sub = os.path.join(str(tmp_path), "nested")
        os.makedirs(sub)
        make_file(str(tmp_path), "root.txt", b"r")
        make_file(sub, "child.txt", b"c")
        hashes, _ = hash_folder_mp(str(tmp_path))
        assert xxhash_of(b"r") in hashes
        assert xxhash_of(b"c") in hashes

    def test_return_type(self, tmp_path):
        make_file(str(tmp_path), "t.txt", b"t")
        result = hash_folder_mp(str(tmp_path))
        assert isinstance(result, tuple) and len(result) == 2
        assert isinstance(result[0], dict) and isinstance(result[1], str)

    def test_deterministic_folder_hash(self, tmp_path):
        make_file(str(tmp_path), "f.txt", b"same")
        _, hash1 = hash_folder_mp(str(tmp_path))
        _, hash2 = hash_folder_mp(str(tmp_path))
        assert hash1 == hash2


class TestEdgeCases:
    def test_empty_dir_returns_empty_dict(self, tmp_path):
        hashes, folder_hash = hash_folder_mp(str(tmp_path))
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
        hashes, _ = hash_folder_mp(str(tmp_path))
        assert len(hashes) == 1
        assert xxhash_of(b"public") in hashes

    def test_broken_symlink_skipped_real_file_included(self, tmp_path, capsys):
        os.symlink("/no/target", os.path.join(str(tmp_path), "broken.lnk"))
        make_file(str(tmp_path), "real.txt", b"real")
        hashes, _ = hash_folder_mp(str(tmp_path))
        assert xxhash_of(b"real") in hashes

    def test_hash_collision_one_entry(self, tmp_path):
        # Two files with identical content — dict has one entry; documented behaviour
        make_file(str(tmp_path), "a.txt", b"same")
        make_file(str(tmp_path), "b.txt", b"same")
        hashes, _ = hash_folder_mp(str(tmp_path))
        assert len(hashes) == 1
        assert hashes[xxhash_of(b"same")] in ("a.txt", "b.txt")

    def test_only_subdirectories_no_files(self, tmp_path):
        os.makedirs(os.path.join(str(tmp_path), "empty_sub"))
        hashes, _ = hash_folder_mp(str(tmp_path))
        assert hashes == {}


class TestHashHashes:
    def test_empty_dict_returns_string(self):
        result = hash_hashes({})
        assert isinstance(result, str) and len(result) > 0

    def test_same_dict_produces_same_hash(self):
        d = {"abc123": "some/path.txt", "def456": "other.txt"}
        assert hash_hashes(d) == hash_hashes(d)
