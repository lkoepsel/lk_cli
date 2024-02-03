import click
import os
from py_cli.utils import get_folders, read_json


@click.command()
@click.version_option("0.4", prog_name="fhc")
@click.argument('folder1', type=click.Path(exists=True, file_okay=False))
@click.argument('folder2', type=click.Path(exists=True, file_okay=False))
def fhc(folder1, folder2):
    """
    Compare two folders by examining the hash file for each of its
    subfolders.

    The process would be:
    \b
    1. For both folders, hw subfolders. This is preferably performed
    at a much earlier date.
    2. Run fhc folder1 folder2

    """

    subfolders1 = (get_folders(folder1))
    subfolders2 = (get_folders(folder2))

    no_match = []
    missing = []
    subfolders2.sort()
    for folder in subfolders2:
        if folder in subfolders1:
            json1 = read_json(os.path.join(folder1, folder))
            json2 = read_json(os.path.join(folder2, folder))

            if json1[os.path.join(folder1, folder)]\
                    != json2[os.path.join(folder2, folder)]:
                click.secho(f'{folder} does not match', fg='red')
                no_match.append(folder)

        else:
            click.secho(f"{folder}, is missing in, {folder1}", fg='magenta')
            missing.append(folder)

    subfolders1.sort()
    for folder in subfolders1:
        if folder not in subfolders2:
            click.secho(f"{folder}, is missing in, {folder2}", fg='yellow')
            missing.append(folder)
