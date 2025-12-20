def main():
    try:
        import click
    except ImportError:
        click = None

    if click is None:
        print("Please install the 'click' Python package to access the CLI!")
        return None

    from .cli_main import chipstream_cli
    return chipstream_cli()
