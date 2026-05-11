#!/usr/bin/env python3
"""
fu: Forth Upload
Upload a Forth source file to a Forth-based ATmega328p board via serial port.
Sends each line and waits for the 'ok' prompt before continuing.
Port defaults to /dev/ttyUSB0 at 250000 baud (matches 'tio forth' profile).
"""

import time
import click
import serial
from lk_cli.utils import get_version

FORTH_PORT = "/dev/ttyUSB0"
FORTH_BAUD = 250000
_OK_TIMEOUT = 5.0
_LINE_DELAY_MS = 50  # ms between lines inside a colon definition


def is_blank_or_comment(line: str) -> bool:
    """Return True for empty lines and lines whose only content is a \\ comment."""
    stripped = line.strip()
    return not stripped or stripped.startswith("\\")


def _opens_definition(line: str) -> bool:
    """True when the first token starts a colon definition."""
    tokens = line.split()
    return bool(tokens) and tokens[0] in (":", ":noname")


def _closes_definition(line: str) -> bool:
    """True when the line contains the ; that ends a colon definition."""
    return ";" in line.split()


def _wait_for_ok(ser, timeout: float) -> tuple[bool, str]:
    """
    Read from ser until a response line contains an 'ok*' token (e.g. 'ok',
    'ok<#,ram>', 'ok<#,flash>') or a line ends with '?' (Forth error).
    Returns (success, response_text).
    """
    start = time.monotonic()
    buf = b""
    while time.monotonic() - start < timeout:
        if ser.in_waiting:
            buf += ser.read(ser.in_waiting)
        else:
            chunk = ser.read(1)
            if chunk:
                buf += chunk
        text = buf.decode("ascii", errors="replace")
        for resp_line in text.splitlines():
            stripped = resp_line.strip()
            tokens = stripped.split()
            if any(t.startswith("ok") for t in tokens):
                return True, text
            if stripped.endswith("?"):
                return False, text
    return False, buf.decode("ascii", errors="replace")


@click.command()
@click.version_option(get_version(), prog_name="fu")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--port", "-p",
    default=FORTH_PORT,
    show_default=True,
    help="Serial port device",
)
@click.option(
    "--baud", "-b",
    default=FORTH_BAUD,
    show_default=True,
    type=int,
    help="Baud rate",
)
@click.option(
    "--timeout", "-t",
    default=_OK_TIMEOUT,
    show_default=True,
    type=float,
    help="Per-line timeout in seconds waiting for 'ok'",
)
@click.option(
    "--delay", "-d",
    default=_LINE_DELAY_MS,
    show_default=True,
    type=int,
    help="Delay in ms between lines inside a colon definition (prevents ring-buffer overflow)",
)
@click.option("--verbose", "-v", is_flag=True, help="Print each line as it is sent")
def fu(file, port, baud, timeout, delay, verbose):
    """
    fu: Forth Upload
    Upload a Forth source file to a serial Forth board.

    Skips blank lines and comment-only lines (lines starting with \\).
    Inside a colon definition, each line is sent with a configurable delay
    so the board's serial ring buffer does not overflow.  After the closing
    ';' (and after any top-level word), waits for the Forth 'ok' prompt
    before continuing.  Handles FlashForth's extended prompt (ok<#,ram>).

    Examples:
      fu blink.fs
      fu --port /dev/ttyACM0 blink.fs
      fu --delay 100 --verbose myapp.fth
    """
    lines = open(file).read().splitlines()
    code_lines = [l for l in lines if not is_blank_or_comment(l)]
    line_delay = delay / 1000.0

    if not code_lines:
        click.echo(f"Uploaded 0 lines from {file}")
        return

    try:
        with serial.Serial(port, baud, timeout=timeout) as ser:
            time.sleep(0.1)
            ser.reset_input_buffer()

            depth = 0
            for lineno, line in enumerate(lines, 1):
                if is_blank_or_comment(line):
                    continue

                stripped = line.rstrip()
                ser.write((stripped + "\r\n").encode())

                if verbose:
                    click.echo(f"[{lineno:4d}] {stripped}")

                if _opens_definition(stripped):
                    depth += 1
                if _closes_definition(stripped):
                    depth = max(0, depth - 1)

                if depth > 0:
                    # Inside a definition the board is in compilation mode and
                    # gives no per-line response.  Pace sends to prevent the
                    # ATmega328p serial ring buffer from overflowing, then
                    # drain any echoed characters before the next send.
                    time.sleep(line_delay)
                    if ser.in_waiting:
                        ser.read(ser.in_waiting)
                else:
                    # At interpreter level (including after the closing ';'):
                    # wait for the Forth 'ok' (or 'ok<#,ram>' etc.) prompt.
                    ok, response = _wait_for_ok(ser, timeout)
                    if not ok:
                        click.echo(
                            f"Error on line {lineno}: {stripped}", err=True
                        )
                        if response.strip():
                            click.echo(f"  Response: {response.strip()}", err=True)
                        raise SystemExit(1)

    except serial.SerialException as exc:
        click.echo(f"Serial error: {exc}", err=True)
        raise SystemExit(1)

    click.echo(f"Uploaded {len(code_lines)} lines from {file}")


if __name__ == "__main__":
    fu()
