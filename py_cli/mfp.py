import click
from py_cli.utils import hash_folder_mp


@click.command()
@click.version_option("0.4", prog_name="mfp")
@click.argument('folder1', type=click.Path(exists=True, file_okay=False))
@click.argument('folder2', type=click.Path(exists=True, file_okay=False))
def mfp(folder1, folder2):
    """
    Compare two folders using hashes. Uses multiprocessing and
    xxHash64 for speed.

    """
    folder1_hashes = hash_folder_mp(folder1)
    folder2_hashes = hash_folder_mp(folder2)

    missing_in_folder1 = []
    missing_in_folder2 = []

    # Comparing the folders with progress bar for folder1
    with click.progressbar(folder1_hashes[0].items(),
                           label=f"Processing {folder1}") as bar:
        for filehash, relpath in bar:
            if filehash not in folder2_hashes[0]:
                missing_in_folder2.append(relpath)

    if len(missing_in_folder2) > 0:
        click.echo(f"Missing in {folder2}")
        for file in missing_in_folder2:
            click.echo(f"{file}")

    # Comparing the folders with progress bar for folder2
    with click.progressbar(folder2_hashes[0].items(),
                           label=f"Processing {folder2}") as bar:
        for filehash, relpath in bar:
            if filehash not in folder1_hashes[0]:
                missing_in_folder1.append(relpath)

    if len(missing_in_folder1) > 0:
        click.echo(f"Missing in {folder1}")
        for file in missing_in_folder1:
            click.echo(f"{file}")
