import click
import os
import shutil
import send2trash as _send2trash
import subprocess
import threading
from lk_cli.utils import get_version


def parse_folder2(output_file):
    """Extract the Folder2 path from a dbc results file."""
    with open(output_file) as f:
        for line in f:
            if line.startswith("Folder2 (checked):"):
                return line.split(":", 1)[1].strip()
    return None


def parse_missing_files(output_file):
    """Extract file paths from the Missing section of a dbc results file."""
    missing = []
    in_missing = False
    with open(output_file) as f:
        for line in f:
            if line.startswith("Missing (not found"):
                in_missing = True
                continue
            if in_missing:
                stripped = line.strip()
                if not stripped or not line.startswith("  "):
                    break
                missing.append(stripped)
    return missing


def remove_from_output(output_file, filepath):
    """Remove the line for filepath from the dbc results file."""
    with open(output_file) as f:
        lines = f.readlines()
    with open(output_file, "w") as f:
        f.writelines(l for l in lines if l.strip() != filepath)


def trash_file(filepath):
    """Move filepath to the system Trash."""
    _send2trash.send2trash(filepath)


def save_image(filepath, folder2):
    """Move filepath into <parent of folder2>/Saved/<dated folder from image path>/."""
    dated_folder = os.path.basename(os.path.dirname(filepath))
    save_dir = os.path.join(os.path.dirname(folder2), "Saved", dated_folder)
    os.makedirs(save_dir, exist_ok=True)
    shutil.move(filepath, os.path.join(save_dir, os.path.basename(filepath)))


def _restore_focus(app_name):
    """Move qlmanage window to the left edge, then re-activate the terminal."""
    import time
    time.sleep(0.5)
    subprocess.run(
        ["osascript", "-e", """
            tell application "System Events"
                set theProcess to first process whose name is "qlmanage"
                if (count of windows of theProcess) > 0 then
                    set position of window 1 of theProcess to {0, 25}
                end if
            end tell
        """],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["osascript", "-e", f'tell application "{app_name}" to activate'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def show_image(filepath):
    """Open filepath in Quick Look and immediately restore terminal focus."""
    result = subprocess.run(
        ["osascript", "-e",
         "tell application \"System Events\" to get name of first process whose frontmost is true"],
        capture_output=True,
        text=True,
    )
    terminal_app = result.stdout.strip()

    proc = subprocess.Popen(
        ["qlmanage", "-p", filepath],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    threading.Thread(target=_restore_focus, args=(terminal_app,), daemon=True).start()
    return proc


@click.command()
@click.version_option(get_version(), prog_name="dbi")
@click.argument("output_file", type=click.Path(exists=True, dir_okay=False))
def dbi(output_file):
    """
    dbi: database image inspector
    Review images listed as missing in a dbc results file.
    Opens each image in the default viewer and waits for a keypress:

    \b
    l — leave (keep the file, advance to next)
    d — delete (move to Trash, remove from results file)
    s — save (move to Saved/YYYY_MM_DD/ alongside folder2, remove from results file)
    q — quit

    The results file is updated in place as files are deleted or saved, so the
    tool can be re-run on the same file to continue reviewing remaining images.
    """
    folder2 = parse_folder2(output_file)
    missing = parse_missing_files(output_file)

    if not missing:
        click.echo("No missing files found in the output file.")
        return

    click.echo(f"Found {len(missing)} missing file(s). Review each below.")
    click.echo("Keys: [l]eave  [d]elete → Trash  [s]ave → Saved/  [q]uit")
    click.echo()

    kept = 0
    deleted = 0
    saved = 0
    i = 0
    while i < len(missing):
        filepath = missing[i]

        if not os.path.exists(filepath):
            click.echo(f"  [{i+1}/{len(missing)}] Not found (skipping): {filepath}")
            i += 1
            continue

        click.echo(f"  [{i+1}/{len(missing)}] {filepath}")
        proc = show_image(filepath)

        while True:
            key = click.getchar()
            if key == "l":
                proc.terminate()
                click.echo("             → kept")
                kept += 1
                i += 1
                break
            elif key == "d":
                proc.terminate()
                try:
                    trash_file(filepath)
                    remove_from_output(output_file, filepath)
                    missing.pop(i)
                    click.echo("             → moved to Trash")
                    deleted += 1
                except Exception as e:
                    click.echo(f"             → Error: {e}")
                    i += 1
                break
            elif key == "s":
                proc.terminate()
                try:
                    save_image(filepath, folder2)
                    remove_from_output(output_file, filepath)
                    missing.pop(i)
                    click.echo("             → saved")
                    saved += 1
                except Exception as e:
                    click.echo(f"             → Error: {e}")
                    i += 1
                break
            elif key == "q":
                proc.terminate()
                click.echo("\nQuit.")
                click.echo(
                    f"Session: {kept} kept, {deleted} deleted, {saved} saved, "
                    f"{len(missing) - i} remaining."
                )
                return
            # any other key: silently ignore and wait for the next keypress

    click.echo(f"\nDone. {kept} kept, {deleted} deleted, {saved} saved.")
