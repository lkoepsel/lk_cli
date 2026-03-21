import click
from lk_cli.utils import hash_folder_mp, get_version, get_pool


@click.command()
@click.version_option(get_version(), prog_name="mf2")
@click.argument("folder1", type=click.Path(exists=True, file_okay=False))
@click.argument("folder2", type=click.Path(exists=True, file_okay=False))
def mf2(folder1, folder2):
    """
    mf2: missing files (one-way)
    List files in folder2 that do not exist in folder1.
    Uses multiprocessing and xxHash64 for speed.

    """
    with get_pool() as pool:
        folder1_hashes = hash_folder_mp(folder1, pool=pool)
        folder2_hashes = hash_folder_mp(folder2, pool=pool)

    missing = [
        relpath
        for filehash, relpath in folder2_hashes[0].items()
        if filehash not in folder1_hashes[0]
    ]

    if missing:
        click.echo(f"Files in {folder2} not found in {folder1}:")
        for file in sorted(missing):
            click.echo(f"  {file}")
    else:
        click.echo(f"All files in {folder2} exist in {folder1}")
