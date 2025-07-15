import click
from lk_cli.utils import hash_folder_mp, get_version


@click.command()
@click.version_option(get_version(), prog_name="mf")
@click.argument("folder1", type=click.Path(exists=True, file_okay=False))
@click.argument("folder2", type=click.Path(exists=True, file_okay=False))
def mf(folder1, folder2):
    """
    mf: missing files
    Very fast! Compare two folders using hashes. Uses multiprocessing and
    xxHash64 for speed.

    """
    folder1_hashes = hash_folder_mp(folder1)
    folder2_hashes = hash_folder_mp(folder2)

    missing_in_folder1 = []
    missing_in_folder2 = []

    for filehash, relpath in folder1_hashes[0].items():
        if filehash not in folder2_hashes[0]:
            missing_in_folder2.append(relpath)

    if len(missing_in_folder2) > 0:
        click.echo(f"Missing in {folder2}")
        for file in missing_in_folder2:
            click.echo(f"{file}")
    else:
        click.echo(f"No files missing in {folder2}")

    for filehash, relpath in folder2_hashes[0].items():
        if filehash not in folder1_hashes[0]:
            missing_in_folder1.append(relpath)

    if len(missing_in_folder1) > 0:
        click.echo(f"Missing in {folder1}")
        for file in missing_in_folder1:
            click.echo(f"{file}")
    else:
        click.echo(f"No files missing in {folder1}")
