import click
from utils import hash_folder


BLOCKSIZE = 1048576


@click.command()
@click.version_option("0.2", prog_name="mf")
@click.argument('folder1', type=click.Path(exists=True, file_okay=False))
@click.argument('folder2', type=click.Path(exists=True, file_okay=False))
def mf(folder1, folder2):
    """Compare two folders using xxHash64."""
    folder1_hashes = hash_folder(folder1)
    folder2_hashes = hash_folder(folder2)

    # Comparing the folders
    for filehash, relpath in folder1_hashes.items():
        if filehash not in folder2_hashes:
            print(f"File {relpath} is not in {folder2}")
        elif folder2_hashes[filehash] != relpath:
            print(f"File {relpath} differs")

    for filehash, relpath in folder2_hashes.items():
        if filehash not in folder1_hashes:
            print(f"File {relpath} is not in {folder1}")
