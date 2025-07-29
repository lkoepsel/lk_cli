import click
import importlib
from lk_cli.utils import get_version


@click.command()
@click.version_option(get_version(), prog_name="lk_cli")
def lk_cli():
    """
    lk_cli: Python CLI utilities collection
    Lists all installed CLI utilities and their descriptions.
    """
    utilities = ["ch", "dedup", "fhc", "hc", "hp", "hw", "mf", "mfs", "uc"]

    click.echo(
        click.style(
            """
           Utilities and Their Descriptions:
           (run lk_cli --help to see this list again)
           """,
            fg="green",
            bold=True,
        )
    )
    click.echo()

    for util in utilities:
        try:
            # Import the module
            module = importlib.import_module(f"lk_cli.{util}")

            # Get the click command object
            command = getattr(module, util, None)

            if command and isinstance(command, click.Command):
                name = util
                doc = command.help or "No description available"

                click.echo(click.style(f"{name}:", fg="blue", bold=True))
                click.echo(f"{doc}\n")
            else:
                click.echo(click.style(f"{util}:", fg="yellow"))
                click.echo("Not a Click command\n")

        except ImportError:
            click.echo(click.style(f"{util}:", fg="red"))
            click.echo("Unable to import module\n")


if __name__ == "__main__":
    lk_cli()
