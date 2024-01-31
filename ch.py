import click
import datetime
import json
import os
from utils import last_modified_file


ignore_files = ['.DS_Store']


# Function to convert timestamp to a readable format
def format_timestamp(timestamp):
    return datetime.datetime.fromtimestamp(
        timestamp).strftime('%Y-%m-%d %H:%M:%S')


@click.command()
@click.version_option("0.4", prog_name="ch")
@click.argument('folder', type=click.Path(exists=True, file_okay=False))
def ch(folder):
    changed_file = last_modified_file(folder)

    # Read and process the JSON file
    try:
        with open(os.path.join(folder, '.hash.json'), 'r') as file:
            data = json.load(file)

            if changed_file[0] > data['last_modified_file_date']:
                if changed_file[1] != '.hash.json':
                    click.echo(
                        f"{changed_file[1]} has changed, since hash")

    except Exception as e:
        print(f"Error occurred: {e}")
