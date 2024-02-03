import click
import datetime
import json
import os
from py_cli.utils import last_modified_file


ignore_files = ['.DS_Store', '.hash.json']


# Function to convert timestamp to a readable format
def format_timestamp(timestamp):
    return datetime.datetime.fromtimestamp(
        timestamp).strftime('%Y-%m-%d %H:%M:%S')


@click.command()
@click.version_option("0.4", prog_name="ch")
@click.argument('folders', nargs=-1,
                type=click.Path(exists=True, file_okay=False))
def ch(folders):
    with click.progressbar(folders) as progressbar:
        for folder in progressbar:
            changed = last_modified_file(folder)

            # Read and process the JSON file
            try:
                with open(os.path.join(folder, '.hash.json'), 'r') as file:
                    data = json.load(file)

                    if changed[0] > data['last_modified_file_date']:
                        if os.path.basename(changed[1]) not in ignore_files:
                            click.echo(
                                f"{changed[1]} has changed, since hash")

            except Exception as e:
                print(f"Error occurred: {e}")
