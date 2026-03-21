import click
from datetime import datetime
import os
from lk_cli.utils import hash_folder_mp, write_json, get_version, get_pool


@click.command()
@click.version_option(get_version(), prog_name="hw")
@click.argument("folders", nargs=-1, type=click.Path(exists=True, file_okay=False))
def hw(folders):
    """
    hw: hash write
    Write hash of each file in folder to a hashes.json
    file in folder. Uses multiprocessing and xxHash64 for speed.

    """
    with get_pool() as pool:
        with click.progressbar(folders) as progressbar:
            for folder in progressbar:
                folder_hashes, folder_hash, last_file = hash_folder_mp(folder, pool=pool)
                write_json(folder, ".hashes.json", folder_hashes)

                hash = {}
                hash[folder] = folder_hash
                hash["folder_last_modified_date"] = os.path.getmtime(folder)
                hash["last_modified_file"] = last_file[1]
                hash["last_modified_file_date"] = last_file[0]
                hash["last_hash_date"] = datetime.now().timestamp()
                write_json(folder, ".hash.json", hash)
