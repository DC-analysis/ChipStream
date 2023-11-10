try:
    import PyQt6
except ImportError:
    PyQt6 = None


if PyQt6 is None:
    def main(*args, **kwargs):
        print("Please install 'chipstream[gui]' to access the GUI!")
else:
    def main():
        print("This is chipstream.")
