from importlib import import_module, resources
import logging
import pathlib
import signal
import sys
import traceback
import webbrowser

from PyQt6 import uic, QtCore, QtWidgets

from .._version import version


class ChipStream(QtWidgets.QMainWindow):
    plots_changed = QtCore.pyqtSignal()

    def __init__(self, *arguments):
        """Initialize ChipStream GUI

        If you pass the "--version" command line argument, the
        application will print the version after initialization
        and exit.
        """
        QtWidgets.QMainWindow.__init__(self)
        ref_ui = resources.files("chipstream.gui") / "main_window.ui"
        with resources.as_file(ref_ui) as path_ui:
            uic.loadUi(path_ui, self)

        self.logger = logging.getLogger(__name__)
        self.manager = self.tableView_input.model.manager

        # Settings are stored in the .ini file format. Even though
        # `self.settings` may return integer/bool in the same session,
        # in the next session, it will reliably return strings. Lists
        # of strings (comma-separated) work nicely though.
        QtCore.QCoreApplication.setOrganizationName("DC-Analysis")
        QtCore.QCoreApplication.setOrganizationDomain(
            "https://github.com/DC-analysis")
        QtCore.QCoreApplication.setApplicationName("ChipStream")
        QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
        #: ChipStream settings
        self.settings = QtCore.QSettings()
        # GUI
        self.setWindowTitle(f"ChipStream {version}")
        # Disable native menu bar (e.g. on Mac)
        self.menubar.setNativeMenuBar(False)
        # File menu
        self.actionQuit.triggered.connect(self.on_action_quit)
        # Help menu
        self.actionDocumentation.triggered.connect(self.on_action_docs)
        self.actionSoftware.triggered.connect(self.on_action_software)
        self.actionAbout.triggered.connect(self.on_action_about)

        # Command button
        self.commandLinkButton_run.clicked.connect(self.on_run)

        # if "--version" was specified, print the version and exit
        if "--version" in arguments:
            print(version)
            QtWidgets.QApplication.processEvents(
                QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
            sys.exit(0)

        # finalize
        self.show()
        self.activateWindow()
        self.setWindowState(QtCore.Qt.WindowState.WindowActive)

    def append_paths(self, path_list):
        """Add input paths to the table"""
        for pp in path_list:
            self.tableView_input.add_input_path(pp)

    @QtCore.pyqtSlot(QtCore.QEvent)
    def dragEnterEvent(self, e):
        """Whether files are accepted"""
        if e.mimeData().hasUrls():
            e.accept()
        else:
            e.ignore()

    @QtCore.pyqtSlot(QtCore.QEvent)
    def dropEvent(self, e):
        """Add dropped files to view"""
        urls = e.mimeData().urls()
        pathlist = []
        for ff in urls:
            pp = pathlib.Path(ff.toLocalFile())
            if pp.is_dir():
                for pi in pp.rglob("*.rtdc"):
                    pathlist.append(pi)
            elif pp.suffix == ".rtdc":
                pathlist.append(pp)
        self.append_paths(pathlist)

    @QtCore.pyqtSlot()
    def on_action_about(self) -> None:
        """Show imprint."""
        gh = "DC-analysis/ChipStream"
        rtd = "chipstream.readthedocs.io"
        about_text = (f"GUI for DC data postprocessing (background "
                      f"computation, segmentation, feature extraction)<br><br>"
                      f"Author: Paul Müller and others<br>"
                      f"GitHub: "
                      f"<a href='https://github.com/{gh}'>{gh}</a><br>"
                      f"Documentation: "
                      f"<a href='https://{rtd}'>{rtd}</a><br>")  # noqa 501
        QtWidgets.QMessageBox.about(self,
                                    f"ChipStream {version}",
                                    about_text)

    @QtCore.pyqtSlot()
    def on_action_docs(self):
        webbrowser.open("https://chipstream.readthedocs.io")

    @QtCore.pyqtSlot()
    def on_action_software(self) -> None:
        """Show used software packages and dependencies."""
        libs = ["dcnum",
                "h5py",
                "numpy",
                ]

        sw_text = f"ChipStream {version}\n\n"
        sw_text += f"Python {sys.version}\n\n"
        sw_text += "Modules:\n"
        for lib in libs:
            try:
                mod = import_module(lib)
            except ImportError:
                pass
            else:
                sw_text += f"- {mod.__name__} {mod.__version__}\n"
        sw_text += f"- PyQt6 {QtCore.QT_VERSION_STR}\n"

        QtWidgets.QMessageBox.information(self, "Software", sw_text)

    @QtCore.pyqtSlot()
    def on_action_quit(self) -> None:
        """Determine what happens when the user wants to quit"""
        QtCore.QCoreApplication.quit()

    @QtCore.pyqtSlot()
    def on_run(self):
        # When we start running, we disable all the controls until we are
        # finished. The user can still add items to the list but not
        # change the pipeline.
        self.widget_options.setEnabled(False)
        self.manager.start()


def excepthook(etype, value, trace):
    """
    Handler for all unhandled exceptions.

    :param `etype`: the exception type (`SyntaxError`,
        `ZeroDivisionError`, etc...);
    :type `etype`: `Exception`
    :param string `value`: the exception error message;
    :param string `trace`: the traceback header, if any (otherwise, it
        prints the standard Python header: ``Traceback (most recent
        call last)``.
    """
    vinfo = f"Unhandled exception in ChipStream version {version}:\n"
    tmp = traceback.format_exception(etype, value, trace)
    exception = "".join([vinfo]+tmp)
    try:
        # Write to the control logger, so errors show up in the
        # chipstream-warnings log.
        main = get_main()
        main.control.logger.error(exception)
    except BaseException:
        # If we send things to the logger and everything is really bad
        # (e.g. cannot write to output hdf5 file or so, then we silently
        # ignore this issue and only print the error message below.
        pass
    QtWidgets.QMessageBox.critical(
        None,
        "ChipStream encountered an error",
        exception
    )


def get_main():
    app = QtWidgets.QApplication.instance()
    for widget in app.topLevelWidgets():
        if isinstance(widget, QtWidgets.QMainWindow):
            return widget


# Make Ctr+C close the app
signal.signal(signal.SIGINT, signal.SIG_DFL)
# Display exception hook in separate dialog instead of crashing
sys.excepthook = excepthook
