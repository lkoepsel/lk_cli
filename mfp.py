import click
from utils import hash_folder_mp


@click.command()
@click.version_option("0.2", prog_name="mfp")
@click.argument('folder1', type=click.Path(exists=True, file_okay=False))
@click.argument('folder2', type=click.Path(exists=True, file_okay=False))
def mf(folder1, folder2):
    """
    Compare two folders using hashes. Uses multiprocessing and
    xxHash64 for speed.

    """
    folder1_hashes = hash_folder_mp(folder1)
    folder2_hashes = hash_folder_mp(folder2)

    # Comparing the folders
    click.echo(f"Missing in {folder2}")
    for filehash, relpath in folder1_hashes.items():
        if filehash not in folder2_hashes:
            print(f"{relpath}")

    click.echo(f"Missing in {folder1}")
    for filehash, relpath in folder2_hashes.items():
        if filehash not in folder1_hashes:
            print(f"{relpath}")
