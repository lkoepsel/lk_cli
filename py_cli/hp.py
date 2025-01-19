import click
import os
from py_cli.utils import hash_folder_mp, get_version


@click.command()
@click.version_option(get_version(), prog_name="hp")
@click.argument("files", nargs=-1, type=click.Path(exists=True, dir_okay=False))
def hp(files):
    """
    Print hash of each specified file to the screen.
    Uses xxHash64 for speed.
    """
    with click.progressbar(files) as progressbar:
        for file_path in progressbar:
            # We'll reuse hash_folder_mp but with the file's parent directory
            folder = os.path.dirname(file_path) or "."
            folder_hashes, _ = hash_folder_mp(folder)

            # Only print the hash for the specified file
            file_name = os.path.basename(file_path)
            if file_name in folder_hashes:
                click.echo(f"{file_path}: {folder_hashes[file_name]}")


if __name__ == "__main__":
    hp()
