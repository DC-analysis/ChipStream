import atexit
from importlib import import_module, resources
import inspect
import logging
import multiprocessing as mp
import pathlib
import signal
import sys
import traceback
import webbrowser

from dcnum.feat import feat_background
from PyQt6 import uic, QtCore, QtWidgets
from PyQt6.QtCore import QStandardPaths

from ..path_cache import PathCache
from .._version import version

from . import splash


class ChipStream(QtWidgets.QMainWindow):
    run_completed = QtCore.pyqtSignal()

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

        # Populate segmenter combobox
        self.comboBox_segmenter.blockSignals(True)
        self.comboBox_segmenter.clear()
        self.comboBox_segmenter.addItem("Disabled (from input file)", "copy")
        self.comboBox_segmenter.addItem("Threshold-based", "thresh")
        self.comboBox_segmenter.blockSignals(False)
        self.comboBox_segmenter.setCurrentIndex(1)

        # Maximum CPU count
        self.spinBox_procs.setMaximum(mp.cpu_count())
        self.spinBox_procs.setValue(mp.cpu_count())

        # Settings are stored in the .ini file format. Even though
        # `self.settings` may return integer/bool in the same session,
        # in the next session, it will reliably return strings. Lists
        # of strings (comma-separated) work nicely though.
        QtCore.QCoreApplication.setOrganizationName("DC-Analysis")
        QtCore.QCoreApplication.setOrganizationDomain("mpl.mpg.de")
        QtCore.QCoreApplication.setApplicationName("ChipStream")
        QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
        #: ChipStream settings
        self.settings = QtCore.QSettings()
        # GUI
        self.setWindowTitle(f"ChipStream {version}")
        # Disable native menu bar (e.g. on Mac)
        self.menubar.setNativeMenuBar(False)

        # File menu
        self.actionAdd.triggered.connect(self.on_action_add)
        self.actionClear.triggered.connect(self.on_action_clear)
        self.actionQuit.triggered.connect(self.on_action_quit)
        # Help menu
        self.actionDocumentation.triggered.connect(self.on_action_docs)
        self.actionSoftware.triggered.connect(self.on_action_software)
        self.actionAbout.triggered.connect(self.on_action_about)

        # Command button
        self.commandLinkButton_run.clicked.connect(self.on_run)

        # Path selection
        cache_loc = pathlib.Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.CacheLocation))
        cache_loc.mkdir(parents=True, exist_ok=True)
        self.path_cache = PathCache(cache_loc / "output_paths.txt")
        atexit.register(self.path_cache.cleanup)
        self.comboBox_output.clear()
        self.comboBox_output.addItem("Output alongside input files", "input")
        for ii, path in enumerate(self.path_cache):
            self.comboBox_output.addItem(str(path), ii)
        self.comboBox_output.addItem("Select output directory", "new")
        self.comboBox_output.currentIndexChanged.connect(self.on_path_out)

        # Signals
        self.run_completed.connect(self.on_run_completed)
        self.tableView_input.row_selected.connect(self.on_select_job)

        # if "--version" was specified, print the version and exit
        if "--version" in arguments:
            print(version)
            QtWidgets.QApplication.processEvents(
                QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
            sys.exit(0)

        # Create a timer that continuously updates self.textBrowser
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.tableView_input.on_selection_changed)
        self.timer.start(1000)

        splash.splash_close()

        # finalize
        self.show()
        self.activateWindow()
        self.setWindowState(QtCore.Qt.WindowState.WindowActive)

    def append_paths(self, path_list):
        """Add input paths to the table"""
        if not self.manager.is_busy():
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

    def get_job_kwargs(self):
        # did the user select a pixel size?
        if self.checkBox_pixel_size.isChecked():
            data_kwargs = {"pixel_size": self.doubleSpinBox_pixel_size.value()}
        else:
            data_kwargs = None

        # default background computer is "sparsemed"
        bg_default = feat_background.BackgroundSparseMed
        bg_kwargs = inspect.getfullargspec(
            bg_default.check_user_kwargs).kwonlydefaults
        bg_kwargs["offset_correction"] = \
            self.checkBox_bg_flickering.isChecked()

        # populate segmenter and its kwargs
        segmenter = self.comboBox_segmenter.currentData()
        segmenter_kwargs = {}
        if segmenter == "thresh":
            segmenter_kwargs["thresh"] = self.spinBox_thresh.value()

        job_kwargs = {
            "data_code": "hdf",
            "data_kwargs": data_kwargs,
            "background_code": bg_default.get_ppid_code(),
            "background_kwargs": bg_kwargs,
            "segmenter_code": segmenter,
            "segmenter_kwargs": segmenter_kwargs,
            "feature_code": "legacy",
            "feature_kwargs": {
                "brightness": self.checkBox_feat_bright.isChecked(),
                "haralick": self.checkBox_feat_haralick.isChecked(),
                "volume": self.checkBox_feat_volume.isChecked(),
                },
            "gate_code": "norm",
            "gate_kwargs": {},
            "num_procs": self.spinBox_procs.value(),
        }

        # special case for copy-segmenter
        if segmenter == "copy":
            job_kwargs["no_basins_in_output"] = \
                not self.checkBox_basin_based.isChecked()

        return job_kwargs

    def is_running(self):
        return self.manager.is_alive()

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
    def on_action_add(self):
        """Open dialog to add files and directories"""
        pathlist, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            'Select DC data',
            '',
            'RT-DC data (*.rtdc)')
        if pathlist:
            # add to list
            self.append_paths(pathlist)

    @QtCore.pyqtSlot()
    def on_action_clear(self):
        """Clear the current table view"""
        self.manager.clear()

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
    def on_path_out(self):
        data = self.comboBox_output.currentData()
        if data == "input":
            # Store output data alongside input data
            self.manager.set_output_path(None)
        elif data == "new":
            # New output path
            default = "." if len(self.path_cache) == 0 else self.path_cache[-1]
            # Open a directory selection dialog
            path = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                "Choose data output directory",
                str(default),
            )
            self.comboBox_output.blockSignals(True)
            if path and pathlib.Path(path).exists():
                self.comboBox_output.insertItem(
                    len(self.path_cache) + 1,  # index in combobox
                    path,
                    len(self.path_cache),  # user data == index in path_cache
                    )
                self.comboBox_output.setCurrentIndex(len(self.path_cache) + 1)
                self.path_cache.add_path(pathlib.Path(path))
                self.manager.set_output_path(path)
            else:
                # User pressed cancel
                self.comboBox_output.setCurrentIndex(0)
                self.manager.set_output_path(None)
            self.comboBox_output.blockSignals(False)
        else:
            # Data is an integer index for `self.path_cache`
            self.manager.set_output_path(self.path_cache[data])
        print(self.manager._path_out)

    @QtCore.pyqtSlot()
    def on_run(self):
        """Run the analysis"""
        # When we start running, we disable all the controls until we are
        # finished. The user can still add items to the list but not
        # change the pipeline.
        self.widget_options.setEnabled(False)
        self.manager.run_all_in_thread(
            job_kwargs=self.get_job_kwargs(),
            callback_when_done=self.run_completed.emit)

    @QtCore.pyqtSlot()
    def on_run_completed(self):
        self.widget_options.setEnabled(True)

    @QtCore.pyqtSlot(int)
    def on_select_job(self, row):
        if row < 0:
            info = "No job selected."
        else:
            # Display some information in the lower text box.
            info = self.manager.get_info(row)
        # Compare the text to the current text.
        old_text = self.textBrowser.toPlainText()
        if info != old_text:
            sb = self.textBrowser.verticalScrollBar()
            is_at_end = sb.maximum() - sb.value() <= 10
            self.textBrowser.setText(info)
            if info.strip().startswith(old_text.strip()) and is_at_end:
                # Automatically scroll to the bottom
                sb.setValue(sb.maximum())


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
