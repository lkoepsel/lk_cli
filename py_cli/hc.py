import click
import os
from py_cli.utils import get_folders, read_hashes, get_version


@click.command()
@click.version_option(get_version(), prog_name="hc")
@click.argument("folder1", type=click.Path(exists=True, file_okay=False))
@click.argument("folder2", type=click.Path(exists=True, file_okay=False))
def hc(folder1, folder2):
    """
    Compare two folders by examining the hashes of the files in each folder

    The process is:
    \b
    1. For both folders, 'hw folder'. This is preferably performed
    at a much earlier date.
    \b
    2. Run hc folder1 folder2

    """

    hashes1 = read_hashes(folder1)
    hashes2 = read_hashes(folder2)

    click.echo(f"Comparing {folder1} to {folder2}")

    no_match = []
    missing = []
    try:
        for filehash, filename in hashes2.items():
            if filehash in hashes1:
                if hashes1[hash] != filename:
                    click.secho(f"{hash} does not match", fg="red")
                    no_match.append(filename)
            else:
                click.secho(f"{filename}, is missing in, {folder2}", fg="magenta")
                missing.append(filename)

    except KeyError:
        click.echo("KeyError: The following parameters were in play:")
        click.echo(f"{json1=} {json2=}")
        click.echo(f"{folder1=} {folder2=} {folder=}")

    for filehash, filename in hashes1.items():
        if filehash not in hashes2:
            click.secho(f"{filename}, is missing in, {folder1}", fg="yellow")
            missing.append(filename)
