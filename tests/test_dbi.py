import os
import pytest
from click.testing import CliRunner
from unittest.mock import patch, call, MagicMock


# ── helpers ───────────────────────────────────────────────────────────────────

def make_output_file(path, missing=None):
    """Create a minimal dbc-style results file."""
    missing = missing or []
    lines = [
        "dbc Results",
        "Generated:           2026-01-01 00:00:00",
        "Folder1 (reference): /f1",
        "Folder2 (checked):   /f2",
        "",
        "Summary",
        "-" * 50,
        f"  Missing:        {len(missing):5d}  (not found by any method)",
        "",
    ]
    if missing:
        lines.append(f"Missing (not found by hash, EXIF, or pHash): {len(missing)}")
        for p in missing:
            lines.append(f"  {p}")
        lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path


def invoke(output_file, keys=()):
    """Invoke dbi with mocked show_image and getchar."""
    from lk_cli.dbi import dbi
    with patch("lk_cli.dbi.show_image"):
        with patch("click.getchar", side_effect=list(keys)):
            return CliRunner().invoke(dbi, [str(output_file)])


# ── parse_missing_files ───────────────────────────────────────────────────────

class TestParseMissingFiles:
    def test_returns_list_of_paths(self, tmp_path):
        f = make_output_file(str(tmp_path / "out.txt"), missing=["/f2/a.jpg", "/f2/b.jpg"])
        from lk_cli.dbi import parse_missing_files
        assert parse_missing_files(f) == ["/f2/a.jpg", "/f2/b.jpg"]

    def test_empty_when_no_missing_section(self, tmp_path):
        f = tmp_path / "out.txt"
        f.write_text("dbc Results\n\nSummary\n")
        from lk_cli.dbi import parse_missing_files
        assert parse_missing_files(str(f)) == []

    def test_single_file(self, tmp_path):
        f = make_output_file(str(tmp_path / "out.txt"), missing=["/path/photo.jpg"])
        from lk_cli.dbi import parse_missing_files
        assert parse_missing_files(f) == ["/path/photo.jpg"]

    def test_stops_at_blank_line(self, tmp_path):
        # Blank line after the list must end the section
        f = make_output_file(str(tmp_path / "out.txt"), missing=["/f2/a.jpg"])
        from lk_cli.dbi import parse_missing_files
        assert parse_missing_files(f) == ["/f2/a.jpg"]

    def test_stops_at_next_section_header(self, tmp_path):
        # A non-indented line immediately after paths should also stop parsing
        content = (
            "dbc Results\n\n"
            "Missing (not found by hash, EXIF, or pHash): 1\n"
            "  /f2/a.jpg\n"
            "Matched by EXIF only: 0\n"
        )
        f = tmp_path / "out.txt"
        f.write_text(content)
        from lk_cli.dbi import parse_missing_files
        assert parse_missing_files(str(f)) == ["/f2/a.jpg"]


# ── remove_from_output ────────────────────────────────────────────────────────

class TestRemoveFromOutput:
    def test_removes_target_path(self, tmp_path):
        f = make_output_file(str(tmp_path / "out.txt"), missing=["/f2/a.jpg", "/f2/b.jpg"])
        from lk_cli.dbi import remove_from_output, parse_missing_files
        remove_from_output(f, "/f2/a.jpg")
        assert parse_missing_files(f) == ["/f2/b.jpg"]

    def test_removes_only_matching_line(self, tmp_path):
        f = make_output_file(str(tmp_path / "out.txt"), missing=["/f2/a.jpg", "/f2/b.jpg"])
        from lk_cli.dbi import remove_from_output
        remove_from_output(f, "/f2/a.jpg")
        assert "/f2/a.jpg" not in open(f).read()

    def test_leaves_other_content_intact(self, tmp_path):
        f = make_output_file(str(tmp_path / "out.txt"), missing=["/f2/a.jpg", "/f2/b.jpg"])
        from lk_cli.dbi import remove_from_output
        remove_from_output(f, "/f2/a.jpg")
        content = open(f).read()
        assert "/f2/b.jpg" in content
        assert "Summary" in content
        assert "dbc Results" in content

    def test_idempotent_on_unknown_path(self, tmp_path):
        f = make_output_file(str(tmp_path / "out.txt"), missing=["/f2/a.jpg"])
        from lk_cli.dbi import remove_from_output, parse_missing_files
        remove_from_output(f, "/f2/ghost.jpg")
        assert parse_missing_files(f) == ["/f2/a.jpg"]


# ── command: no missing section ───────────────────────────────────────────────

class TestDbiNoMissing:
    def test_exits_cleanly(self, tmp_path):
        f = make_output_file(str(tmp_path / "out.txt"), missing=[])
        from lk_cli.dbi import dbi
        result = CliRunner().invoke(dbi, [str(f)])
        assert result.exit_code == 0

    def test_reports_no_missing(self, tmp_path):
        f = make_output_file(str(tmp_path / "out.txt"), missing=[])
        from lk_cli.dbi import dbi
        result = CliRunner().invoke(dbi, [str(f)])
        assert "No missing" in result.output


# ── command: keypress behaviour ───────────────────────────────────────────────

class TestDbiKeys:
    def test_l_leaves_file_in_place(self, tmp_path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"data")
        f = make_output_file(str(tmp_path / "out.txt"), missing=[str(img)])
        result = invoke(f, keys="l")
        assert img.exists()
        assert "kept" in result.output

    def test_l_does_not_alter_output_file(self, tmp_path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"data")
        f = make_output_file(str(tmp_path / "out.txt"), missing=[str(img)])
        invoke(f, keys="l")
        from lk_cli.dbi import parse_missing_files
        assert parse_missing_files(f) == [str(img)]

    def test_q_quits_immediately(self, tmp_path):
        img1 = tmp_path / "a.jpg"
        img1.write_bytes(b"data")
        img2 = tmp_path / "b.jpg"
        img2.write_bytes(b"data")
        f = make_output_file(str(tmp_path / "out.txt"), missing=[str(img1), str(img2)])
        result = invoke(f, keys="q")
        assert "Quit" in result.output

    def test_q_shows_only_first_image(self, tmp_path):
        img1 = tmp_path / "a.jpg"
        img1.write_bytes(b"data")
        img2 = tmp_path / "b.jpg"
        img2.write_bytes(b"data")
        f = make_output_file(str(tmp_path / "out.txt"), missing=[str(img1), str(img2)])
        with patch("lk_cli.dbi.show_image") as mock_show:
            with patch("click.getchar", side_effect=["q"]):
                CliRunner().invoke(
                    __import__("lk_cli.dbi", fromlist=["dbi"]).dbi, [str(f)]
                )
        mock_show.assert_called_once()

    def test_unknown_key_is_ignored(self, tmp_path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"data")
        f = make_output_file(str(tmp_path / "out.txt"), missing=[str(img)])
        result = invoke(f, keys="xl")   # 'x' ignored, 'l' acts
        assert "kept" in result.output

    def test_multiple_unknown_keys_before_action(self, tmp_path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"data")
        f = make_output_file(str(tmp_path / "out.txt"), missing=[str(img)])
        result = invoke(f, keys="xxzl")
        assert "kept" in result.output


# ── command: delete behaviour ─────────────────────────────────────────────────

class TestDbiDelete:
    def test_d_calls_trash_file(self, tmp_path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"data")
        f = make_output_file(str(tmp_path / "out.txt"), missing=[str(img)])
        with patch("lk_cli.dbi.show_image"):
            with patch("lk_cli.dbi.trash_file") as mock_trash:
                with patch("click.getchar", side_effect=["d"]):
                    CliRunner().invoke(
                        __import__("lk_cli.dbi", fromlist=["dbi"]).dbi, [str(f)]
                    )
        mock_trash.assert_called_once_with(str(img))

    def test_d_removes_line_from_output_file(self, tmp_path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"data")
        f = make_output_file(str(tmp_path / "out.txt"), missing=[str(img)])
        with patch("lk_cli.dbi.show_image"):
            with patch("lk_cli.dbi.trash_file"):
                with patch("click.getchar", side_effect=["d"]):
                    CliRunner().invoke(
                        __import__("lk_cli.dbi", fromlist=["dbi"]).dbi, [str(f)]
                    )
        from lk_cli.dbi import parse_missing_files
        assert parse_missing_files(f) == []

    def test_d_shows_trash_message(self, tmp_path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"data")
        f = make_output_file(str(tmp_path / "out.txt"), missing=[str(img)])
        with patch("lk_cli.dbi.show_image"):
            with patch("lk_cli.dbi.trash_file"):
                with patch("click.getchar", side_effect=["d"]):
                    result = CliRunner().invoke(
                        __import__("lk_cli.dbi", fromlist=["dbi"]).dbi, [str(f)]
                    )
        assert "Trash" in result.output

    def test_d_continues_to_next_file(self, tmp_path):
        img1 = tmp_path / "a.jpg"
        img1.write_bytes(b"data")
        img2 = tmp_path / "b.jpg"
        img2.write_bytes(b"data")
        f = make_output_file(str(tmp_path / "out.txt"), missing=[str(img1), str(img2)])
        with patch("lk_cli.dbi.show_image") as mock_show:
            with patch("lk_cli.dbi.trash_file"):
                with patch("click.getchar", side_effect=["d", "l"]):
                    CliRunner().invoke(
                        __import__("lk_cli.dbi", fromlist=["dbi"]).dbi, [str(f)]
                    )
        assert mock_show.call_count == 2


# ── command: missing files on disk ────────────────────────────────────────────

class TestDbiMissingOnDisk:
    def test_nonexistent_file_is_skipped(self, tmp_path):
        f = make_output_file(
            str(tmp_path / "out.txt"), missing=["/nonexistent/ghost.jpg"]
        )
        from lk_cli.dbi import dbi
        result = CliRunner().invoke(dbi, [str(f)])
        assert result.exit_code == 0
        assert "Not found" in result.output

    def test_nonexistent_file_does_not_open_viewer(self, tmp_path):
        f = make_output_file(
            str(tmp_path / "out.txt"), missing=["/nonexistent/ghost.jpg"]
        )
        with patch("lk_cli.dbi.show_image") as mock_show:
            CliRunner().invoke(
                __import__("lk_cli.dbi", fromlist=["dbi"]).dbi, [str(f)]
            )
        mock_show.assert_not_called()


# ── command: process lifecycle ────────────────────────────────────────────────

class TestDbiProcessLifecycle:
    def test_process_terminated_on_leave(self, tmp_path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"data")
        f = make_output_file(str(tmp_path / "out.txt"), missing=[str(img)])
        mock_proc = MagicMock()
        with patch("lk_cli.dbi.show_image", return_value=mock_proc):
            with patch("click.getchar", side_effect=["l"]):
                from lk_cli.dbi import dbi
                CliRunner().invoke(dbi, [str(f)])
        mock_proc.terminate.assert_called_once()

    def test_process_terminated_on_delete(self, tmp_path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"data")
        f = make_output_file(str(tmp_path / "out.txt"), missing=[str(img)])
        mock_proc = MagicMock()
        with patch("lk_cli.dbi.show_image", return_value=mock_proc):
            with patch("lk_cli.dbi.trash_file"):
                with patch("click.getchar", side_effect=["d"]):
                    from lk_cli.dbi import dbi
                    CliRunner().invoke(dbi, [str(f)])
        mock_proc.terminate.assert_called_once()

    def test_process_terminated_on_quit(self, tmp_path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"data")
        f = make_output_file(str(tmp_path / "out.txt"), missing=[str(img)])
        mock_proc = MagicMock()
        with patch("lk_cli.dbi.show_image", return_value=mock_proc):
            with patch("click.getchar", side_effect=["q"]):
                from lk_cli.dbi import dbi
                CliRunner().invoke(dbi, [str(f)])
        mock_proc.terminate.assert_called_once()


# ── command: session summary ──────────────────────────────────────────────────

class TestDbiSummary:
    def test_done_message_shown_after_all_reviewed(self, tmp_path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"data")
        f = make_output_file(str(tmp_path / "out.txt"), missing=[str(img)])
        result = invoke(f, keys="l")
        assert "Done" in result.output

    def test_summary_counts_kept_and_deleted(self, tmp_path):
        img1 = tmp_path / "a.jpg"
        img1.write_bytes(b"data")
        img2 = tmp_path / "b.jpg"
        img2.write_bytes(b"data")
        f = make_output_file(str(tmp_path / "out.txt"), missing=[str(img1), str(img2)])
        with patch("lk_cli.dbi.show_image"):
            with patch("lk_cli.dbi.trash_file"):
                with patch("click.getchar", side_effect=["l", "d"]):
                    result = CliRunner().invoke(
                        __import__("lk_cli.dbi", fromlist=["dbi"]).dbi,
                        [str(f)],
                    )
        assert "1 kept" in result.output
        assert "1 deleted" in result.output

    def test_quit_shows_remaining_count(self, tmp_path):
        img1 = tmp_path / "a.jpg"
        img1.write_bytes(b"data")
        img2 = tmp_path / "b.jpg"
        img2.write_bytes(b"data")
        f = make_output_file(str(tmp_path / "out.txt"), missing=[str(img1), str(img2)])
        result = invoke(f, keys="q")
        assert "remaining" in result.output
