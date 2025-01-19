import click
from py_cli.utils import get_version, calculate_file_hash, shorten_path


@click.command()
@click.version_option(get_version(), prog_name="hp")
@click.argument("files", nargs=-1, type=click.Path(exists=True, dir_okay=False))
def hp(files):
    """
    Print hash of each specified file to the screen.
    Uses xxHash64 for speed.
    """
    for file_path in files:
        file_hash = calculate_file_hash(file_path)
        shortened_path = shorten_path(file_path)
        click.echo(f"{shortened_path}: {file_hash}")


if __name__ == "__main__":
    hp()
