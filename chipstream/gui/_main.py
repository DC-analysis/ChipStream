def main():
    # https://github.com/pytorch/pytorch/issues/166628
    import os
    import platform
    if platform.system() == "Windows":
        import ctypes
        from importlib.util import find_spec
        try:
            if (spec := find_spec("torch")) and spec.origin and os.path.exists(
                    dll_path := os.path.join(os.path.dirname(spec.origin),
                                             "lib", "c10.dll")
            ):
                ctypes.CDLL(os.path.normpath(dll_path))
        except Exception:
            pass

    class DevNull:
        """Effectively a file-like object for piping everything to nothing."""

        def write(self, *args, **kwargs):
            pass

    try:
        import PyQt6
    except ImportError:
        PyQt6 = None

    if PyQt6 is None:
        print("Please install 'chipstream[gui]' to access the GUI!")
        return None

    from importlib import resources
    import multiprocessing as mp
    import sys
    from PyQt6 import QtWidgets, QtCore, QtGui

    mp.freeze_support()

    # In case we have a frozen application, and we encounter errors
    # in subprocesses, then these will try to print everything to stdout
    # and stderr. However, if we compiled the app with PyInstaller with
    # the --noconsole option, sys.stderr and sys.stdout are None and
    # an exception is raised, breaking the program.
    if sys.stdout is None:
        sys.stdout = DevNull()
    if sys.stderr is None:
        sys.stderr = DevNull()

    from .main_window import ChipStream

    app = QtWidgets.QApplication(sys.argv)
    ref_ico = resources.files("chipstream.gui.img") / "chipstream_icon.png"
    with resources.as_file(ref_ico) as path_icon:
        app.setWindowIcon(QtGui.QIcon(str(path_icon)))

    # Use dots as decimal separators
    QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.c()))

    window = ChipStream(*app.arguments()[1:])  # noqa: F841

    return sys.exit(app.exec())
