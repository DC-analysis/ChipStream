try:
    import click
except ImportError:
    click = None

if click is None:
    def main(*args, **kwargs):
        print("Please install the 'click' Python package to access the CLI!")
else:
    from .cli_main import chipstream_cli as main  # noqa: F401
