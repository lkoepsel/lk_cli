import click
from py_cli.mf import mf
from py_cli.ch import ch
from py_cli.fhc import fhc
from py_cli.hw import hw
from py_cli.mfs import mfs


@click.group()
def cli():
    pass


cli.add_command(mf)
cli.add_command(ch)
cli.add_command(fhc)
cli.add_command(hw)
cli.add_command(mfs)

if __name__ == "__main__":
    cli()
