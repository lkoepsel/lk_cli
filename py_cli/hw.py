import click
from datetime import datetime
import json
import os
import re
import xxhash
from multiprocessing import Pool
from functools import partial
from py_cli.utils import last_modified_file

dot_file = re.compile(r'^\.')
BLOCKSIZE = 1048576
CORES = 8


def write_json(folder, name, dict):
    with open(os.path.join(folder, name), 'w') as hash_file:
        json.dump(dict, hash_file, indent=4)


def hash_file(filepath):
    """Generate xxHash64 of a file."""
    hasher = xxhash.xxh64()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(BLOCKSIZE), b""):
            hasher.update(byte_block)
    return hasher.hexdigest()


def process_file(root, folder_path, file):
    """Process a single file for hashing."""
    if not dot_file.match(file):
        filepath = os.path.join(root, file)
        relpath = os.path.relpath(filepath, folder_path)
        file_hash = hash_file(filepath)
        return file_hash, relpath
    return None


def hash_folder(folder_path):
    """Generate hashes for all files in a folder."""
    hashes = {}
    with Pool(CORES) as pool:
        for root, _, files in os.walk(folder_path):
            results = pool.map(partial(process_file, root, folder_path), files)
            for result in results:
                if result:
                    file_hash, relpath = result
                    hashes[file_hash] = relpath
    return hashes, hash_hashes(hashes)


def hash_hashes(hashes):
    """Generate a hash of the folder of hashes."""
    hasher = xxhash.xxh64()
    for hash_text in hashes:
        hasher.update(hash_text.encode('utf-8'))
    hash_of_folder = hasher.hexdigest()
    return(hash_of_folder)


@click.command()
@click.version_option("0.1", prog_name="hw")
@click.argument('folder', type=click.Path(exists=True, file_okay=False))
def hw(folder):
    """
    Write hash of each file in folder to a hashes.json
    file in folder. Uses multiprocessing and xxHash64 for speed.

    """
    folder_hashes, folder_hash = hash_folder(folder)
    write_json(folder, '.hashes.json', folder_hashes)

    hash = {}
    hash[folder] = folder_hash
    hash['folder_last_modified_date'] = os.path.getmtime(folder)
    last_file = last_modified_file(folder)
    hash['last_modified_file'] = last_file[1]
    hash['last_modified_file_date'] = last_file[0]
    hash['last_hash_date'] = datetime.now().timestamp()
    write_json(folder, '.hash.json', hash)
