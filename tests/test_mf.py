import os
import pytest
from click.testing import CliRunner
from unittest.mock import patch


def _hashes(folder, relpaths):
    """Build a fake hash_folder_mp return value with sequential hashes."""
    h = {str(i): relpaths[i] for i in range(len(relpaths))}
    return h, None, [0, None]


class TestMfFullPaths:
    def test_missing_in_folder2_shows_full_path(self, tmp_path):
        f1 = tmp_path / "f1"
        f2 = tmp_path / "f2"
        f1.mkdir(); f2.mkdir()
        from lk_cli.mf import mf
        with patch("lk_cli.mf.hash_folder_mp") as mock_hash, \
             patch("lk_cli.mf.get_pool") as mock_pool:
            mock_pool.return_value.__enter__ = lambda s, *a: None
            mock_pool.return_value.__exit__ = lambda s, *a: None
            mock_hash.side_effect = [
                _hashes(str(f1), ["sub/only_in_f1.jpg"]),
                _hashes(str(f2), []),
            ]
            result = CliRunner().invoke(mf, [str(f1), str(f2)])
        assert os.path.join(str(f1), "sub/only_in_f1.jpg") in result.output

    def test_missing_in_folder1_shows_full_path(self, tmp_path):
        f1 = tmp_path / "f1"
        f2 = tmp_path / "f2"
        f1.mkdir(); f2.mkdir()
        from lk_cli.mf import mf
        with patch("lk_cli.mf.hash_folder_mp") as mock_hash, \
             patch("lk_cli.mf.get_pool") as mock_pool:
            mock_pool.return_value.__enter__ = lambda s, *a: None
            mock_pool.return_value.__exit__ = lambda s, *a: None
            mock_hash.side_effect = [
                _hashes(str(f1), []),
                _hashes(str(f2), ["sub/only_in_f2.jpg"]),
            ]
            result = CliRunner().invoke(mf, [str(f1), str(f2)])
        assert os.path.join(str(f2), "sub/only_in_f2.jpg") in result.output

    def test_no_bare_relpath_in_output(self, tmp_path):
        f1 = tmp_path / "f1"
        f2 = tmp_path / "f2"
        f1.mkdir(); f2.mkdir()
        from lk_cli.mf import mf
        with patch("lk_cli.mf.hash_folder_mp") as mock_hash, \
             patch("lk_cli.mf.get_pool") as mock_pool:
            mock_pool.return_value.__enter__ = lambda s, *a: None
            mock_pool.return_value.__exit__ = lambda s, *a: None
            mock_hash.side_effect = [
                _hashes(str(f1), ["sub/photo.jpg"]),
                _hashes(str(f2), []),
            ]
            result = CliRunner().invoke(mf, [str(f1), str(f2)])
        assert "\nsub/photo.jpg\n" not in result.output


class TestMf2FullPaths:
    def test_missing_shows_full_path(self, tmp_path):
        f1 = tmp_path / "f1"
        f2 = tmp_path / "f2"
        f1.mkdir(); f2.mkdir()
        from lk_cli.mf2 import mf2
        with patch("lk_cli.mf2.hash_folder_mp") as mock_hash, \
             patch("lk_cli.mf2.get_pool") as mock_pool:
            mock_pool.return_value.__enter__ = lambda s, *a: None
            mock_pool.return_value.__exit__ = lambda s, *a: None
            mock_hash.side_effect = [
                _hashes(str(f1), []),
                _hashes(str(f2), ["dated/photo.jpg"]),
            ]
            result = CliRunner().invoke(mf2, [str(f1), str(f2)])
        assert os.path.join(str(f2), "dated/photo.jpg") in result.output

    def test_no_bare_relpath_in_output(self, tmp_path):
        f1 = tmp_path / "f1"
        f2 = tmp_path / "f2"
        f1.mkdir(); f2.mkdir()
        from lk_cli.mf2 import mf2
        with patch("lk_cli.mf2.hash_folder_mp") as mock_hash, \
             patch("lk_cli.mf2.get_pool") as mock_pool:
            mock_pool.return_value.__enter__ = lambda s, *a: None
            mock_pool.return_value.__exit__ = lambda s, *a: None
            mock_hash.side_effect = [
                _hashes(str(f1), []),
                _hashes(str(f2), ["dated/photo.jpg"]),
            ]
            result = CliRunner().invoke(mf2, [str(f1), str(f2)])
        assert "\ndated/photo.jpg\n" not in result.output
