import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, call
import serial


def make_serial_mock(responses):
    """
    Build a mock serial.Serial context manager.
    responses: list of bytes that in_waiting/read will return in sequence.
    """
    mock_ser = MagicMock()
    mock_ser.__enter__ = lambda s: s
    mock_ser.__exit__ = MagicMock(return_value=False)

    # Each response is returned on successive read() calls
    mock_ser.in_waiting = 1
    mock_ser.read.side_effect = responses
    return mock_ser


class TestFuCommand:
    def test_help_exits_zero(self):
        from lk_cli.fu import fu
        result = CliRunner().invoke(fu, ["--help"])
        assert result.exit_code == 0
        assert "serial" in result.output.lower() or "forth" in result.output.lower()

    def test_missing_file_exits_nonzero(self):
        from lk_cli.fu import fu
        result = CliRunner().invoke(fu, ["/nonexistent/file.fth"])
        assert result.exit_code != 0

    def test_opens_correct_default_port_and_baud(self, tmp_path):
        from lk_cli.fu import fu, FORTH_PORT, FORTH_BAUD
        src = tmp_path / "test.fth"
        src.write_text(": hello ;\n")
        mock_ser = MagicMock()
        mock_ser.__enter__ = lambda s: s
        mock_ser.__exit__ = MagicMock(return_value=False)
        mock_ser.in_waiting = 4
        mock_ser.read.return_value = b" ok\n"
        with patch("lk_cli.fu.serial.Serial", return_value=mock_ser) as mock_cls:
            CliRunner().invoke(fu, [str(src)])
        mock_cls.assert_called_once_with(FORTH_PORT, FORTH_BAUD, timeout=pytest.approx(5.0))

    def test_custom_port_and_baud(self, tmp_path):
        from lk_cli.fu import fu
        src = tmp_path / "test.fth"
        src.write_text(": hello ;\n")
        mock_ser = MagicMock()
        mock_ser.__enter__ = lambda s: s
        mock_ser.__exit__ = MagicMock(return_value=False)
        mock_ser.in_waiting = 4
        mock_ser.read.return_value = b" ok\n"
        with patch("lk_cli.fu.serial.Serial", return_value=mock_ser) as mock_cls:
            CliRunner().invoke(fu, ["--port", "/dev/ttyACM0", "--baud", "115200", str(src)])
        mock_cls.assert_called_once_with("/dev/ttyACM0", 115200, timeout=pytest.approx(5.0))


class TestFuLineHandling:
    def _run_with_ok(self, tmp_path, content, verbose=False):
        from lk_cli.fu import fu
        src = tmp_path / "test.fth"
        src.write_text(content)
        mock_ser = MagicMock()
        mock_ser.__enter__ = lambda s: s
        mock_ser.__exit__ = MagicMock(return_value=False)
        mock_ser.in_waiting = 4
        mock_ser.read.return_value = b" ok\n"
        args = [str(src)]
        if verbose:
            args.insert(0, "--verbose")
        with patch("lk_cli.fu.serial.Serial", return_value=mock_ser):
            with patch("lk_cli.fu.time.sleep"):
                result = CliRunner().invoke(fu, args)
        return result, mock_ser

    def test_sends_code_line_with_crlf(self, tmp_path):
        result, mock_ser = self._run_with_ok(tmp_path, ": blink ;\n")
        mock_ser.write.assert_called_once_with(b": blink ;\r\n")

    def test_skips_blank_lines(self, tmp_path):
        result, mock_ser = self._run_with_ok(tmp_path, "\n\n: word ;\n\n")
        assert mock_ser.write.call_count == 1
        mock_ser.write.assert_called_once_with(b": word ;\r\n")

    def test_skips_comment_only_lines(self, tmp_path):
        content = "\\ This is a comment\n: word ;\n\\ another comment\n"
        result, mock_ser = self._run_with_ok(tmp_path, content)
        assert mock_ser.write.call_count == 1
        mock_ser.write.assert_called_once_with(b": word ;\r\n")

    def test_sends_multiple_lines(self, tmp_path):
        content = ": foo ;\n: bar ;\n: baz ;\n"
        result, mock_ser = self._run_with_ok(tmp_path, content)
        assert mock_ser.write.call_count == 3

    def test_exits_zero_on_success(self, tmp_path):
        result, _ = self._run_with_ok(tmp_path, ": hello ;\n")
        assert result.exit_code == 0

    def test_reports_line_count_on_success(self, tmp_path):
        result, _ = self._run_with_ok(tmp_path, ": foo ;\n: bar ;\n")
        assert "2" in result.output

    def test_verbose_shows_lines(self, tmp_path):
        result, _ = self._run_with_ok(tmp_path, ": hello ;\n", verbose=True)
        assert ": hello ;" in result.output

    def test_strips_trailing_whitespace_from_sent_line(self, tmp_path):
        result, mock_ser = self._run_with_ok(tmp_path, ": foo ;   \n")
        mock_ser.write.assert_called_once_with(b": foo ;\r\n")


class TestFuErrorHandling:
    def test_error_response_exits_nonzero(self, tmp_path):
        from lk_cli.fu import fu
        src = tmp_path / "test.fth"
        src.write_text(": bad ;\n")
        mock_ser = MagicMock()
        mock_ser.__enter__ = lambda s: s
        mock_ser.__exit__ = MagicMock(return_value=False)
        mock_ser.in_waiting = 4
        # Return an error response (no 'ok', contains '?')
        mock_ser.read.return_value = b"undefined ?\n"
        with patch("lk_cli.fu.serial.Serial", return_value=mock_ser):
            with patch("lk_cli.fu.time.sleep"):
                result = CliRunner().invoke(fu, [str(src)])
        assert result.exit_code != 0

    def test_serial_exception_exits_nonzero(self, tmp_path):
        from lk_cli.fu import fu
        src = tmp_path / "test.fth"
        src.write_text(": hello ;\n")
        with patch("lk_cli.fu.serial.Serial", side_effect=serial.SerialException("port not found")):
            result = CliRunner().invoke(fu, [str(src)])
        assert result.exit_code != 0
        assert "port not found" in result.output.lower() or "error" in result.output.lower()

    def test_empty_file_succeeds_with_zero_lines(self, tmp_path):
        from lk_cli.fu import fu
        src = tmp_path / "empty.fth"
        src.write_text("")
        mock_ser = MagicMock()
        mock_ser.__enter__ = lambda s: s
        mock_ser.__exit__ = MagicMock(return_value=False)
        with patch("lk_cli.fu.serial.Serial", return_value=mock_ser):
            with patch("lk_cli.fu.time.sleep"):
                result = CliRunner().invoke(fu, [str(src)])
        assert result.exit_code == 0
        mock_ser.write.assert_not_called()


class TestFuMultiLineDefinition:
    """The board only responds with 'ok' after the closing ';', not mid-definition."""

    def _blink_src(self, tmp_path):
        src = tmp_path / "blink.fs"
        src.write_text(
            ": blink ( ms -- )\n"
            "    LED out\n"
            "    begin\n"
            "        LED tog\n"
            "        dup ms\n"
            "    again\n"
            ";\n"
        )
        return src

    def test_no_ok_wait_inside_definition(self, tmp_path):
        from lk_cli.fu import fu
        src = self._blink_src(tmp_path)
        mock_ser = MagicMock()
        mock_ser.__enter__ = lambda s: s
        mock_ser.__exit__ = MagicMock(return_value=False)
        mock_ser.in_waiting = 4
        mock_ser.read.return_value = b"; ok<#,ram>\n"
        with patch("lk_cli.fu.serial.Serial", return_value=mock_ser):
            with patch("lk_cli.fu.time.sleep"):
                result = CliRunner().invoke(fu, [str(src)])
        # 7 lines sent; ok waited only once (after ';' at depth 0)
        assert mock_ser.write.call_count == 7
        assert result.exit_code == 0

    def test_delay_applied_inside_definition(self, tmp_path):
        """time.sleep is called for each line while depth > 0."""
        from lk_cli.fu import fu
        src = self._blink_src(tmp_path)
        mock_ser = MagicMock()
        mock_ser.__enter__ = lambda s: s
        mock_ser.__exit__ = MagicMock(return_value=False)
        mock_ser.in_waiting = 0
        mock_ser.read.return_value = b"; ok<#,ram>\n"
        sleep_calls = []
        with patch("lk_cli.fu.serial.Serial", return_value=mock_ser):
            with patch("lk_cli.fu.time.sleep", side_effect=sleep_calls.append):
                CliRunner().invoke(fu, [str(src)])
        # Initial 0.1s settle + one call per line inside the definition (6 lines)
        in_def_sleeps = [s for s in sleep_calls if s != pytest.approx(0.1)]
        assert len(in_def_sleeps) == 6

    def test_custom_delay_passed_to_sleep(self, tmp_path):
        from lk_cli.fu import fu
        src = self._blink_src(tmp_path)
        mock_ser = MagicMock()
        mock_ser.__enter__ = lambda s: s
        mock_ser.__exit__ = MagicMock(return_value=False)
        mock_ser.in_waiting = 0
        mock_ser.read.return_value = b"; ok<#,ram>\n"
        sleep_calls = []
        with patch("lk_cli.fu.serial.Serial", return_value=mock_ser):
            with patch("lk_cli.fu.time.sleep", side_effect=sleep_calls.append):
                CliRunner().invoke(fu, ["--delay", "100", str(src)])
        in_def_sleeps = [s for s in sleep_calls if s != pytest.approx(0.1)]
        assert all(s == pytest.approx(0.1) for s in in_def_sleeps)

    def test_ok_ram_response_accepted(self, tmp_path):
        """FlashForth responds 'ok<#,ram>' not plain 'ok' — must be accepted."""
        from lk_cli.fu import fu
        src = tmp_path / "test.fth"
        src.write_text(": nop ;\n")
        mock_ser = MagicMock()
        mock_ser.__enter__ = lambda s: s
        mock_ser.__exit__ = MagicMock(return_value=False)
        mock_ser.in_waiting = 18
        mock_ser.read.return_value = b": nop ; ok<#,ram>\n"
        with patch("lk_cli.fu.serial.Serial", return_value=mock_ser):
            with patch("lk_cli.fu.time.sleep"):
                result = CliRunner().invoke(fu, [str(src)])
        assert result.exit_code == 0

    def test_single_line_definition_still_waits_for_ok(self, tmp_path):
        from lk_cli.fu import fu
        src = tmp_path / "test.fth"
        src.write_text(": nop ;\n")
        mock_ser = MagicMock()
        mock_ser.__enter__ = lambda s: s
        mock_ser.__exit__ = MagicMock(return_value=False)
        mock_ser.in_waiting = 4
        mock_ser.read.return_value = b" ok\n"
        with patch("lk_cli.fu.serial.Serial", return_value=mock_ser):
            with patch("lk_cli.fu.time.sleep"):
                result = CliRunner().invoke(fu, [str(src)])
        assert result.exit_code == 0
        mock_ser.write.assert_called_once_with(b": nop ;\r\n")

    def test_top_level_word_after_definition_waits_for_ok(self, tmp_path):
        from lk_cli.fu import fu
        src = tmp_path / "test.fth"
        src.write_text(": foo ;\n500 foo\n")
        ok_responses = iter([b" ok<#,ram>\n", b" ok\n"])
        mock_ser = MagicMock()
        mock_ser.__enter__ = lambda s: s
        mock_ser.__exit__ = MagicMock(return_value=False)
        mock_ser.in_waiting = 4
        mock_ser.read.side_effect = lambda *a, **kw: next(ok_responses)
        with patch("lk_cli.fu.serial.Serial", return_value=mock_ser):
            with patch("lk_cli.fu.time.sleep"):
                result = CliRunner().invoke(fu, [str(src)])
        assert result.exit_code == 0
        assert mock_ser.write.call_count == 2


class TestFuOpensCloses:
    def test_opens_colon(self):
        from lk_cli.fu import _opens_definition
        assert _opens_definition(": blink ( ms -- )") is True
        assert _opens_definition(":noname ( -- )") is True

    def test_opens_false_for_body_lines(self):
        from lk_cli.fu import _opens_definition
        assert _opens_definition("    LED out") is False
        assert _opens_definition(";") is False
        assert _opens_definition("500 blink") is False

    def test_closes_semicolon(self):
        from lk_cli.fu import _closes_definition
        assert _closes_definition(";") is True
        assert _closes_definition(": nop ;") is True

    def test_closes_false_for_other_lines(self):
        from lk_cli.fu import _closes_definition
        assert _closes_definition(": blink ( ms -- )") is False
        assert _closes_definition("    LED tog") is False


class TestFuPipeMode:
    """--pipe writes Forth lines to stdout for use with tio ctrl-t R."""

    BLINK = (
        "\\ comment\n"
        ": blink ( ms -- )\n"
        "    LED out\n"
        "    begin\n"
        "        LED tog\n"
        "        dup ms\n"
        "    again\n"
        ";\n"
        "500 blink\n"
    )

    def _run_pipe(self, tmp_path, content=None, extra_args=None):
        from lk_cli.fu import fu
        src = tmp_path / "blink.fs"
        src.write_text(self.BLINK if content is None else content)
        args = ["--pipe", str(src)] + (extra_args or [])
        with patch("lk_cli.fu.time.sleep"):
            result = CliRunner().invoke(fu, args)
        return result

    def test_does_not_open_serial_port(self, tmp_path):
        with patch("lk_cli.fu.serial.Serial") as mock_cls:
            self._run_pipe(tmp_path)
        mock_cls.assert_not_called()

    def test_exits_zero(self, tmp_path):
        result = self._run_pipe(tmp_path)
        assert result.exit_code == 0

    def test_output_contains_code_lines(self, tmp_path):
        result = self._run_pipe(tmp_path)
        assert ": blink ( ms -- )" in result.output
        assert "LED out" in result.output
        assert "500 blink" in result.output

    def test_output_excludes_comments_and_blanks(self, tmp_path):
        result = self._run_pipe(tmp_path)
        assert "\\ comment" not in result.output

    def test_lines_end_with_bare_cr(self, tmp_path):
        # tio merges stdout+stderr, so we use bare \r (nl=False) with no \n.
        # Spy on click.echo to verify the terminator is \r, not \r\n.
        from lk_cli.fu import fu
        import click as click_mod
        src = tmp_path / "t.fs"
        src.write_text(": foo ;\n")
        echo_msgs = []
        real_echo = click_mod.echo
        def spy(msg="", **kw):
            echo_msgs.append((msg, kw))
            real_echo(msg, **kw)
        with patch("lk_cli.fu.click.echo", side_effect=spy):
            with patch("lk_cli.fu.time.sleep"):
                CliRunner().invoke(fu, ["--pipe", str(src)])
        forth_calls = [(m, kw) for m, kw in echo_msgs if isinstance(m, str) and m.endswith("\r")]
        assert forth_calls, "No call ending with \\r found"
        assert all(kw.get("nl") is False for _, kw in forth_calls)

    def test_delay_applied_to_all_lines(self, tmp_path):
        from lk_cli.fu import fu
        src = tmp_path / "t.fs"
        src.write_text(": foo ;\n42 .\n")
        sleep_calls = []
        with patch("lk_cli.fu.time.sleep", side_effect=sleep_calls.append):
            CliRunner().invoke(fu, ["--pipe", str(src)])
        # Both lines get a delay (no serial feedback to wait for)
        assert len(sleep_calls) == 2

    def test_empty_file_exits_zero_with_no_output(self, tmp_path):
        result = self._run_pipe(tmp_path, content="")
        assert result.exit_code == 0
        assert result.output == ""

    def test_no_status_message_in_output(self, tmp_path):
        # Nothing except Forth lines must reach the device.
        result = self._run_pipe(tmp_path)
        assert "Uploaded" not in result.output
        assert "lines" not in result.output


class TestFuIsBlankOrComment:
    def test_blank_line(self):
        from lk_cli.fu import is_blank_or_comment
        assert is_blank_or_comment("") is True
        assert is_blank_or_comment("   ") is True
        assert is_blank_or_comment("\t") is True

    def test_comment_line(self):
        from lk_cli.fu import is_blank_or_comment
        assert is_blank_or_comment("\\ comment") is True
        assert is_blank_or_comment("  \\ indented comment") is True

    def test_code_line(self):
        from lk_cli.fu import is_blank_or_comment
        assert is_blank_or_comment(": foo ;") is False
        assert is_blank_or_comment("42 .") is False
        assert is_blank_or_comment("( ok )") is False

    def test_inline_comment_not_skipped(self):
        from lk_cli.fu import is_blank_or_comment
        # Lines with code followed by a comment are NOT blank/comment-only
        assert is_blank_or_comment(": foo ; \\ define foo") is False
