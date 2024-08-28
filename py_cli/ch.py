import click
import datetime
import json
import os
from py_cli.utils import last_modified_file


ignore_files = [".DS_Store", ".hash.json"]


# Function to convert timestamp to a readable format
def format_timestamp(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


@click.command()
@click.version_option("0.4", prog_name="ch")
@click.argument("folders", nargs=-1, type=click.Path(exists=True, file_okay=False))
def ch(folders):
    """
    ch: check hash - read existing hash.json and .hashes.josn files
    and confirm hashes for files have not changed. Use to ensure
    hash files are in-sync with folder contents.
    """
    missing_folders = {}
    changed_folders = {}
    with click.progressbar(folders) as progressbar:
        for folder in progressbar:
            changed = last_modified_file(folder)

            with open(os.path.join(folder, ".hashes.json"), "r") as file:
                file_hashes = json.load(file)

                for file_hash, file_name in file_hashes.items():
                    if not os.path.exists(os.path.join(folder, file_name)):
                        if folder not in missing_folders.keys():
                            missing_folders[folder] = [file_name]
                        else:
                            missing_folders[folder].append(file_name)
            # Read and process the JSON file
            try:
                with open(os.path.join(folder, ".hash.json"), "r") as file:
                    folder_hash = json.load(file)

                    if changed[0] > folder_hash["last_modified_file_date"]:
                        if os.path.basename(changed[1]) not in ignore_files:
                            if folder not in changed_folders.keys():
                                changed_folders[folder] = [file_name]

            except Exception as e:
                click.echo(f"Error occurred: {e}")

    if len(missing_folders.keys()) != 0:
        for folder, files in missing_folders.items():
            click.secho(f"{folder} is missing:", fg="magenta")
            for file in files:
                click.secho(f"{file}", fg="magenta")
    if len(changed_folders.keys()) != 0:
        for folder, files in changed_folders.items():
            click.secho(f"{folder} has changed:", fg="yellow")
            for file in files:
                click.secho(f"{file}", fg="yellow")
