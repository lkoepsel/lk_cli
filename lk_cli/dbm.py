import click
import os
import shutil
from lk_cli.utils import get_version

MOVEABLE_SECTIONS = [
    "Hash matches:",
    "Image hash matches:",
    "EXIF matches (re-encoded/edited):",
]


def parse_folder2(results_file):
    """Extract the Folder2 path from a dbc results file."""
    with open(results_file) as f:
        for line in f:
            if line.startswith("Folder2 (checked):"):
                return line.split(":", 1)[1].strip()
    return None


def parse_matched_files(results_file):
    """
    Extract file paths from Hash, Image hash, and EXIF match sections.
    pHash matches and Missing sections are intentionally excluded.
    """
    matched = []
    in_section = False
    with open(results_file) as f:
        for line in f:
            if any(line.startswith(s) for s in MOVEABLE_SECTIONS):
                in_section = True
                continue
            if in_section:
                stripped = line.strip()
                if not stripped or not line.startswith("  "):
                    in_section = False
                else:
                    matched.append(stripped)
    return matched


@click.command()
@click.version_option(get_version(), prog_name="dbm")
@click.argument("results_file", type=click.Path(exists=True, dir_okay=False))
def dbm(results_file):
    """
    dbm: database move
    Move confirmed duplicate files from folder2 to a duplicates subfolder.
    Reads a dbc results file and moves files matched by Hash, Image hash,
    or EXIF — the three high-confidence match types.

    \b
    pHash matches (visually similar only) are NOT moved since they may
    represent different photos. Missing files are also left in place.
    The duplicates/ folder is created inside folder2.
    """
    folder2 = parse_folder2(results_file)
    if not folder2:
        click.echo("Error: could not find Folder2 path in results file.", err=True)
        raise SystemExit(1)

    if not os.path.isdir(folder2):
        click.echo(f"Error: folder2 not found on disk: {folder2}", err=True)
        raise SystemExit(1)

    matched = parse_matched_files(results_file)
    if not matched:
        click.echo("No matched files found to move.")
        return

    dest = os.path.join(folder2, "duplicates")
    os.makedirs(dest, exist_ok=True)

    moved = 0
    skipped = 0
    for filepath in matched:
        if not os.path.exists(filepath):
            click.echo(f"  Skipping (not found): {filepath}")
            skipped += 1
            continue
        dest_path = os.path.join(dest, os.path.basename(filepath))
        if os.path.exists(dest_path):
            base, ext = os.path.splitext(os.path.basename(filepath))
            dest_path = os.path.join(dest, f"{base}_{moved}{ext}")
        shutil.move(filepath, dest_path)
        moved += 1

    click.echo(f"Moved {moved} file(s) to {dest}")
    if skipped:
        click.echo(f"Skipped {skipped} file(s) not found on disk.")
