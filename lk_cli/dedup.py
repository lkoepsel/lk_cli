import click
import os
import shutil
from collections import defaultdict
from lk_cli.utils import hash_file, get_version


@click.command()
@click.version_option(get_version(), prog_name="dedup")
@click.argument("folder", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without actually moving files",
)
def dedup(folder, dry_run):
    """
    dedup: duplicate detector
    Check for duplicate files in a folder using file hashes.
    The most recent file is kept and duplicates are moved to DUPLICATES_DELETE folder on Desktop.
    """
    # Get hashes for all files in the folder and group by hash
    hash_to_files = defaultdict(list)

    for root, _, files in os.walk(folder):
        for file in files:
            # Skip dot files
            if not file.startswith("."):
                filepath = os.path.join(root, file)
                try:
                    file_hash = hash_file(filepath)
                    hash_to_files[file_hash].append(filepath)
                except OSError as e:
                    click.echo(click.style(f"Error reading {filepath}: {e}", fg="red"))
                    continue

    # Find duplicates (hashes with more than one file)
    duplicates = {h: files for h, files in hash_to_files.items() if len(files) > 1}

    if not duplicates:
        click.echo(click.style("No duplicate files found.", fg="green"))
        return

    # Create DUPLICATES_DELETE folder on Desktop
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    duplicates_folder = os.path.join(desktop_path, "DUPLICATES_DELETE")

    if not dry_run:
        os.makedirs(duplicates_folder, exist_ok=True)
        click.echo(f"Created folder: {duplicates_folder}")

    total_duplicates = 0
    total_size_saved = 0

    for file_hash, files in duplicates.items():
        # Sort files by modification time (newest first)
        files_with_mtime = []
        for file_path in files:
            try:
                mtime = os.path.getmtime(file_path)
                size = os.path.getsize(file_path)
                files_with_mtime.append((file_path, mtime, size))
            except OSError as e:
                click.echo(click.style(f"Error accessing {file_path}: {e}", fg="red"))
                continue

        if len(files_with_mtime) <= 1:
            continue

        # Sort by modification time (newest first)
        files_with_mtime.sort(key=lambda x: x[1], reverse=True)

        # Keep the most recent file, move the rest
        keep_file = files_with_mtime[0][0]
        duplicates_to_move = files_with_mtime[1:]

        click.echo(f"\nDuplicate group (hash: {file_hash[:12]}...):")
        click.echo(click.style(f"  KEEPING: {keep_file}", fg="green"))

        for duplicate_file, mtime, size in duplicates_to_move:
            total_duplicates += 1
            total_size_saved += size

            # Generate unique filename in duplicates folder
            filename = os.path.basename(duplicate_file)
            dest_path = os.path.join(duplicates_folder, filename)

            # Handle filename conflicts by adding counter
            counter = 1
            while os.path.exists(dest_path):
                name, ext = os.path.splitext(filename)
                dest_path = os.path.join(duplicates_folder, f"{name}_{counter}{ext}")
                counter += 1

            if dry_run:
                click.echo(
                    click.style(
                        f"  WOULD MOVE: {duplicate_file} -> {dest_path}", fg="yellow"
                    )
                )
            else:
                try:
                    shutil.move(duplicate_file, dest_path)
                    click.echo(
                        click.style(
                            f"  MOVED: {duplicate_file} -> {dest_path}", fg="blue"
                        )
                    )
                except OSError as e:
                    click.echo(
                        click.style(f"  ERROR moving {duplicate_file}: {e}", fg="red")
                    )

    # Summary
    click.echo("\nSummary:")
    if dry_run:
        click.echo(f"  Would move {total_duplicates} duplicate files")
        click.echo(
            f"  Would save {total_size_saved:,} bytes ({total_size_saved / 1024 / 1024:.1f} MB)"
        )
    else:
        click.echo(f"  Moved {total_duplicates} duplicate files")
        click.echo(
            f"  Saved {total_size_saved:,} bytes ({total_size_saved / 1024 / 1024:.1f} MB)"
        )
        click.echo(f"  Duplicates moved to: {duplicates_folder}")
