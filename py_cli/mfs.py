import click  # type: ignore
from py_cli.utils import hash_folder


BLOCKSIZE = 1048576


@click.command()
@click.version_option("0.5", prog_name="mfs")
@click.argument("folder1", type=click.Path(exists=True, file_okay=False))
@click.argument("folder2", type=click.Path(exists=True, file_okay=False))
def mfs(folder1, folder2):
    """
    Uses sequential processing to
    compare two folders using hash of each file for comparison.
    Use mf for higher performance, this version retained for checking.
    """
    folder1_hashes = hash_folder(folder1)
    folder2_hashes = hash_folder(folder2)

    # Comparing the folders
    missing_in_2 = []
    differs_in_2 = []
    for filehash, filepath in folder1_hashes.items():
        if filehash not in folder2_hashes:
            missing_in_2.append(filepath)
        elif folder2_hashes[filehash] != filepath:
            differs_in_2.append(filepath)
    if len(missing_in_2) != 0:
        print(f"{folder2} is missing {len(missing_in_2)} file(s):")
        missing_in_2.sort()
        [print(file) for file in missing_in_2]

    missing_in_1 = []
    for filehash, filepath in folder2_hashes.items():
        if filehash not in folder1_hashes:
            missing_in_1.append(filepath)
    if len(missing_in_1) != 0:
        print(f"\n{folder1} is missing {len(missing_in_1)} file(s):")
        missing_in_1.sort()
        [print(file) for file in missing_in_1]
