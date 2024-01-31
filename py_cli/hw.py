import click
from datetime import datetime
import os
from py_cli.utils import last_modified_file, hash_folder_mp, write_json


@click.command()
@click.version_option("0.1", prog_name="hw")
@click.argument('folders', nargs=-1,
                type=click.Path(exists=True, file_okay=False))
def hw(folders):
    """
    Write hash of each file in folder to a hashes.json
    file in folder. Uses multiprocessing and xxHash64 for speed.

    """
    for folder in folders:
        folder_hashes, folder_hash = hash_folder_mp(folder)
        write_json(folder, '.hashes.json', folder_hashes)

        hash = {}
        hash[folder] = folder_hash
        hash['folder_last_modified_date'] = os.path.getmtime(folder)
        last_file = last_modified_file(folder)
        hash['last_modified_file'] = last_file[1]
        hash['last_modified_file_date'] = last_file[0]
        hash['last_hash_date'] = datetime.now().timestamp()
        write_json(folder, '.hash.json', hash)
