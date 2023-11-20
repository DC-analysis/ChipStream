try:
    import PyQt6
except ImportError:
    PyQt6 = None


if PyQt6 is None:
    def main(*args, **kwargs):
        print("Please install 'chipstream[gui]' to access the GUI!")
else:
    def main():
        from importlib import resources
        import sys
        from PyQt6 import QtWidgets, QtCore, QtGui

        from .main_window import ChipStream

        app = QtWidgets.QApplication(sys.argv)
        ref_ico = resources.files("chipstream.gui.img") / "chipstream_icon.png"
        with resources.as_file(ref_ico) as path_icon:
            app.setWindowIcon(QtGui.QIcon(str(path_icon)))

        # Use dots as decimal separators
        QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.c()))

        window = ChipStream(*sys.argv)  # noqa: F841

        sys.exit(app.exec())
