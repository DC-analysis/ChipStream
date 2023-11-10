try:
    import click
except ImportError:
    click = None


if click is None:
    def main(*args, **kwargs):
        print("Please install the 'click' Python package to access the CLI!")
else:
    @click.command(name="chipstream")
    def main():
        print("This is chipstream.")
