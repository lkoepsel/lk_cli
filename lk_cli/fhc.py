import click
import os
from lk_cli.utils import get_folders, read_hash, get_version


@click.command()
@click.version_option(get_version(), prog_name="fhc")
@click.argument("folder1", type=click.Path(exists=True, file_okay=False))
@click.argument("folder2", type=click.Path(exists=True, file_okay=False))
def fhc(folder1, folder2):
    """
    fhc: Folder Hash Compare (by subfolders)
    Compare two folders by examining the hash files for each of the
    folders, subfolders.

    The process is:
    \b
    1. For both folders, 'hw subfolders'. This is preferably performed
    at a much earlier date.
    \b
    2. Run fhc folder1 folder2

    """

    subfolders1 = get_folders(folder1)
    subfolders2 = get_folders(folder2)

    click.echo(f"Comparing {folder1} to {folder2}")

    no_match = []
    missing = []
    subfolders2.sort()

    # Initialize variables outside try block
    json1 = None
    json2 = None
    current_folder = None

    try:
        for folder in subfolders2:
            current_folder = folder  # Store current folder for error reporting
            if folder in subfolders1:
                json1 = read_hash(os.path.join(folder1, folder))
                json2 = read_hash(os.path.join(folder2, folder))

                if (
                    json1[os.path.join(folder1, folder)]
                    != json2[os.path.join(folder2, folder)]
                ):
                    click.secho(f"{folder} does not match", fg="red")
                    no_match.append(folder)

            else:
                click.secho(f"{folder}, is missing in, {folder1}", fg="magenta")
                missing.append(folder)
    except KeyError:
        click.echo("KeyError: The following parameters were in play:")
        click.echo(f"json1: {json1}")
        click.echo(f"json2: {json2}")
        click.echo(f"folder1: {folder1}")
        click.echo(f"folder2: {folder2}")
        click.echo(f"current folder: {current_folder}")

    subfolders1.sort()
    for folder in subfolders1:
        if folder not in subfolders2:
            click.secho(f"{folder}, is missing in, {folder2}", fg="yellow")
            missing.append(folder)
