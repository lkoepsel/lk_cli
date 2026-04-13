import os
import pytest
from click.testing import CliRunner


# ── helpers ───────────────────────────────────────────────────────────────────

def make_results_file(path, folder2, hash_matches=None, image_matches=None,
                      exif_matches=None, phash_matches=None,
                      missing=None):
    """Create a minimal dbc-style results file for testing dbm."""
    lines = [
        "Folder1 (reference): /f1",
        f"Folder2 (checked):   {folder2}",
        "",
    ]
    if hash_matches:
        lines.append(f"Hash matches: {len(hash_matches)}")
        for p in hash_matches:
            lines.append(f"  {p}")
        lines.append("")
    if image_matches:
        lines.append(f"Image hash matches: {len(image_matches)}")
        for p in image_matches:
            lines.append(f"  {p}")
        lines.append("")
    if exif_matches:
        lines.append(f"EXIF matches (re-encoded/edited): {len(exif_matches)}")
        for p in exif_matches:
            lines.append(f"  {p}")
        lines.append("")
    if phash_matches:
        lines.append(f"pHash matches (Hamming distance ≤ 5): {len(phash_matches)}")
        for p in phash_matches:
            lines.append(f"  {p}  [distance: 2]")
        lines.append("")
    if missing:
        lines.append(f"Missing (not found by hash, EXIF, or pHash): {len(missing)}")
        for p in missing:
            lines.append(f"  {p}")
        lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path


def invoke(results_file):
    from lk_cli.dbm import dbm
    return CliRunner().invoke(dbm, [str(results_file)])


# ── parse_folder2 ─────────────────────────────────────────────────────────────

class TestParseFolder2:
    def test_returns_folder2_path(self, tmp_path):
        f = str(tmp_path / "results.txt")
        make_results_file(f, "/path/to/folder2")
        from lk_cli.dbm import parse_folder2
        assert parse_folder2(f) == "/path/to/folder2"

    def test_returns_none_when_not_found(self, tmp_path):
        f = tmp_path / "results.txt"
        f.write_text("no folder info here\n")
        from lk_cli.dbm import parse_folder2
        assert parse_folder2(str(f)) is None

    def test_handles_path_with_spaces(self, tmp_path):
        f = str(tmp_path / "results.txt")
        make_results_file(f, "/my photos/2024")
        from lk_cli.dbm import parse_folder2
        assert parse_folder2(f) == "/my photos/2024"


# ── parse_matched_files ───────────────────────────────────────────────────────

class TestParseMatchedFiles:
    def test_hash_matches_parsed(self, tmp_path):
        f = str(tmp_path / "results.txt")
        make_results_file(f, "/f2", hash_matches=["/f2/a.jpg", "/f2/b.jpg"])
        from lk_cli.dbm import parse_matched_files
        result = parse_matched_files(f)
        assert "/f2/a.jpg" in result
        assert "/f2/b.jpg" in result

    def test_image_matches_parsed(self, tmp_path):
        f = str(tmp_path / "results.txt")
        make_results_file(f, "/f2", image_matches=["/f2/c.jpg"])
        from lk_cli.dbm import parse_matched_files
        result = parse_matched_files(f)
        assert "/f2/c.jpg" in result

    def test_exif_matches_parsed(self, tmp_path):
        f = str(tmp_path / "results.txt")
        make_results_file(f, "/f2", exif_matches=["/f2/e.jpg"])
        from lk_cli.dbm import parse_matched_files
        result = parse_matched_files(f)
        assert "/f2/e.jpg" in result

    def test_all_three_sections_combined(self, tmp_path):
        f = str(tmp_path / "results.txt")
        make_results_file(f, "/f2",
                          hash_matches=["/f2/a.jpg"],
                          image_matches=["/f2/b.jpg"],
                          exif_matches=["/f2/c.jpg"])
        from lk_cli.dbm import parse_matched_files
        result = parse_matched_files(f)
        assert len(result) == 3

    def test_empty_when_no_sections(self, tmp_path):
        f = str(tmp_path / "results.txt")
        make_results_file(f, "/f2")
        from lk_cli.dbm import parse_matched_files
        assert parse_matched_files(f) == []

    def test_missing_section_not_included(self, tmp_path):
        f = str(tmp_path / "results.txt")
        make_results_file(f, "/f2", missing=["/f2/missing.jpg"])
        from lk_cli.dbm import parse_matched_files
        assert parse_matched_files(f) == []

    def test_phash_section_not_included(self, tmp_path):
        f = str(tmp_path / "results.txt")
        make_results_file(f, "/f2", phash_matches=["/f2/similar.jpg"])
        from lk_cli.dbm import parse_matched_files
        assert parse_matched_files(f) == []


# ── command: error handling ───────────────────────────────────────────────────

class TestDbmErrors:
    def test_error_when_folder2_not_in_file(self, tmp_path):
        f = tmp_path / "results.txt"
        f.write_text("no folder info\n")
        result = invoke(f)
        assert result.exit_code != 0

    def test_error_when_folder2_not_on_disk(self, tmp_path):
        f = str(tmp_path / "results.txt")
        make_results_file(f, "/nonexistent/folder2")
        result = invoke(f)
        assert result.exit_code != 0

    def test_error_message_mentions_folder2(self, tmp_path):
        f = tmp_path / "results.txt"
        f.write_text("no folder info\n")
        result = invoke(f)
        assert "Error" in result.output or "Error" in (result.output + str(result.exception))


# ── command: no matched files ─────────────────────────────────────────────────

class TestDbmNoMatches:
    def test_no_matched_files_message(self, tmp_path):
        folder2 = tmp_path / "folder2"
        folder2.mkdir()
        f = str(tmp_path / "results.txt")
        make_results_file(f, str(folder2))
        result = invoke(f)
        assert result.exit_code == 0
        assert "No matched" in result.output

    def test_no_duplicates_folder_created_when_nothing_to_move(self, tmp_path):
        folder2 = tmp_path / "folder2"
        folder2.mkdir()
        f = str(tmp_path / "results.txt")
        make_results_file(f, str(folder2))
        invoke(f)
        assert not (folder2 / "duplicates").exists()


# ── command: move behaviour ───────────────────────────────────────────────────

class TestDbmMove:
    def test_moves_hash_matched_to_duplicates(self, tmp_path):
        folder2 = tmp_path / "folder2"
        folder2.mkdir()
        img = folder2 / "photo.jpg"
        img.write_bytes(b"data")
        f = str(tmp_path / "results.txt")
        make_results_file(f, str(folder2), hash_matches=[str(img)])
        invoke(f)
        assert (folder2 / "duplicates" / "photo.jpg").exists()
        assert not img.exists()

    def test_moves_image_matched_to_duplicates(self, tmp_path):
        folder2 = tmp_path / "folder2"
        folder2.mkdir()
        img = folder2 / "photo.jpg"
        img.write_bytes(b"data")
        f = str(tmp_path / "results.txt")
        make_results_file(f, str(folder2), image_matches=[str(img)])
        invoke(f)
        assert (folder2 / "duplicates" / "photo.jpg").exists()
        assert not img.exists()

    def test_moves_exif_matched_to_duplicates(self, tmp_path):
        folder2 = tmp_path / "folder2"
        folder2.mkdir()
        img = folder2 / "photo.jpg"
        img.write_bytes(b"data")
        f = str(tmp_path / "results.txt")
        make_results_file(f, str(folder2), exif_matches=[str(img)])
        invoke(f)
        assert (folder2 / "duplicates" / "photo.jpg").exists()
        assert not img.exists()

    def test_creates_duplicates_subfolder(self, tmp_path):
        folder2 = tmp_path / "folder2"
        folder2.mkdir()
        img = folder2 / "photo.jpg"
        img.write_bytes(b"data")
        f = str(tmp_path / "results.txt")
        make_results_file(f, str(folder2), hash_matches=[str(img)])
        invoke(f)
        assert (folder2 / "duplicates").is_dir()

    def test_reports_moved_count(self, tmp_path):
        folder2 = tmp_path / "folder2"
        folder2.mkdir()
        img1 = folder2 / "a.jpg"
        img2 = folder2 / "b.jpg"
        img1.write_bytes(b"data")
        img2.write_bytes(b"data")
        f = str(tmp_path / "results.txt")
        make_results_file(f, str(folder2), hash_matches=[str(img1), str(img2)])
        result = invoke(f)
        assert "2" in result.output

    def test_skips_files_not_on_disk(self, tmp_path):
        folder2 = tmp_path / "folder2"
        folder2.mkdir()
        f = str(tmp_path / "results.txt")
        make_results_file(f, str(folder2), hash_matches=["/nonexistent/ghost.jpg"])
        result = invoke(f)
        assert result.exit_code == 0
        assert "Skipping" in result.output

    def test_reports_skipped_count(self, tmp_path):
        folder2 = tmp_path / "folder2"
        folder2.mkdir()
        img = folder2 / "real.jpg"
        img.write_bytes(b"data")
        f = str(tmp_path / "results.txt")
        make_results_file(f, str(folder2),
                          hash_matches=[str(img), "/nonexistent/ghost.jpg"])
        result = invoke(f)
        assert "Skipped 1" in result.output

    def test_does_not_move_phash_matches(self, tmp_path):
        folder2 = tmp_path / "folder2"
        folder2.mkdir()
        img = folder2 / "similar.jpg"
        img.write_bytes(b"data")
        f = str(tmp_path / "results.txt")
        make_results_file(f, str(folder2), phash_matches=[str(img)])
        invoke(f)
        assert img.exists()
        assert not (folder2 / "duplicates").exists()

    def test_does_not_move_missing_files(self, tmp_path):
        folder2 = tmp_path / "folder2"
        folder2.mkdir()
        img = folder2 / "truly_missing.jpg"
        img.write_bytes(b"data")
        f = str(tmp_path / "results.txt")
        make_results_file(f, str(folder2), missing=[str(img)])
        invoke(f)
        assert img.exists()

    def test_output_reports_destination(self, tmp_path):
        folder2 = tmp_path / "folder2"
        folder2.mkdir()
        img = folder2 / "photo.jpg"
        img.write_bytes(b"data")
        f = str(tmp_path / "results.txt")
        make_results_file(f, str(folder2), hash_matches=[str(img)])
        result = invoke(f)
        assert "duplicates" in result.output
