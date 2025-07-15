import click
from lk_cli.ch import ch
from lk_cli.dedup import dedup
from lk_cli.fhc import fhc
from lk_cli.mf import mf
from lk_cli.hw import hw
from lk_cli.hp import hp
from lk_cli.hc import hc
from lk_cli.mfs import mfs


@click.group()
def cli():
    pass


cli.add_command(ch)
cli.add_command(dedup)
cli.add_command(fhc)
cli.add_command(hc)
cli.add_command(hw)
cli.add_command(hp)
cli.add_command(mf)
cli.add_command(mfs)

if __name__ == "__main__":
    cli()
