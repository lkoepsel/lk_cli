import click
import datetime
import json
import os
from py_cli.utils import last_modified_file, get_version

ignore_files = [".DS_Store", ".hash.json"]


def format_timestamp(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def process_missing_files(folder, file_hashes):
    try:
        missing_files = []
        for file_hash, file_name in file_hashes.items():
            if not os.path.exists(os.path.join(folder, file_name)):
                missing_files.append(file_name)
        return missing_files
    except Exception as e:
        click.secho(f"Error processing missing files: {e}", fg="red", err=True)
        return []


def process_changed_files(folder, changed):
    try:
        with open(os.path.join(folder, ".hash.json"), "r") as file:
            folder_hash = json.load(file)
            if (
                changed[0] > folder_hash["last_modified_file_date"]
                and os.path.basename(changed[1]) not in ignore_files
            ):
                return [changed[1]]
    except Exception as e:
        click.echo(f"Error occurred: {e}")
    return []


def display_results(missing_folders, changed_folders):
    if missing_folders:
        for folder, files in missing_folders.items():
            click.secho(f"{folder} is missing:", fg="magenta")
            for file in files:
                click.secho(f"{file}", fg="magenta")

    if changed_folders:
        for folder, files in changed_folders.items():
            click.secho(f"{folder} has changed:", fg="yellow")
            for file in files:
                click.secho(f"{file}", fg="yellow")


@click.command()
@click.version_option(get_version(), prog_name="ch")
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
            try:
                changed = last_modified_file(folder)

                # Process missing files
                with open(os.path.join(folder, ".hashes.json"), "r") as file:
                    file_hashes = json.load(file)
                    missing_files = process_missing_files(folder, file_hashes)
                    if missing_files:
                        missing_folders[folder] = missing_files

                # Process changed files
                changed_files = process_changed_files(folder, changed)
                if changed_files:
                    changed_folders[folder] = changed_files
            except FileNotFoundError:
                click.secho(f"No .hashes.json found in {folder}", fg="red", err=True)
            except Exception as e:
                click.secho(
                    f"Error processing folder {folder}: {e}", fg="red", err=True
                )

    display_results(missing_folders, changed_folders)
