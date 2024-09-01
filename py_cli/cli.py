import click


@click.command()
def ch():
    """Execute ch command"""
    click.echo("Executing ch")


@click.command()
def fhc():
    """Execute fhc command"""
    click.echo("Executing fhc")


@click.command()
def hw():
    """Execute hw command"""
    click.echo("Executing hw")


@click.command()
def mf():
    """Execute mf command"""
    click.echo("Executing mf")


@click.command()
def mfs():
    """Execute mfs command"""
    click.echo("Executing mfs")


# Group commands if needed
cli = click.Group(
    commands={
        "ch": ch,
        "fhc": fhc,
        "hw": hw,
        "mf": mf,
        "mfs": mfs,
    }
)

if __name__ == "__main__":
    cli()
