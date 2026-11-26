from __future__ import annotations

import atexit
import functools
from importlib import import_module
import importlib.resources
import inspect
import logging
import pathlib
import re
import signal
import sys
import time
import traceback
import webbrowser

from dcnum.common import cpu_count
from dcnum.feat import feat_background
from dcnum.meta import paths as dcnum_paths
import psutil
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QStandardPaths
from torch.cuda import is_available as cuda_is_available

from .. import kwargs_parse
from ..path_cache import PathCache
from .._version import version

from .main_window_ui import Ui_MainWindow
from .dlg_expert import EXPERT_STEPS, ExpertSettingsDialog
from .dlg_model_props import TorchModelProperties
from .manager import ChipStreamJobManager
from . import splash
from .sys_usage import SystemUsageLabel


class ChipStream(QtWidgets.QMainWindow):
    # The PyQt6 stubs do not define a default for `arguments`.
    run_completed = QtCore.pyqtSignal()  # pyright: ignore[reportCallIssue]

    def __init__(self, *arguments):
        """Initialize ChipStream GUI

        If you pass the "--version" command line argument, the
        application will print the version after initialization
        and exit.
        """
        self.job_manager = ChipStreamJobManager()
        QtWidgets.QMainWindow.__init__(self)

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Settings are stored in the .ini file format. Even though
        # `self.settings` may return integer/bool in the same session,
        # in the next session, it will reliably return strings. Lists
        # of strings (comma-separated) work nicely though.
        QtCore.QCoreApplication.setOrganizationName("DC-Analysis")
        QtCore.QCoreApplication.setOrganizationDomain("dc-cosmos.org")
        QtCore.QCoreApplication.setApplicationName("ChipStream")
        QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
        #: ChipStream settings
        self.settings = QtCore.QSettings()

        # register search paths with dcnum
        for path in self.settings.value("segm/torch_model_files", []):
            path = pathlib.Path(path)
            if path.is_dir():
                dcnum_paths.register_search_path("torch_model_files", path)

        self.ui.tableWidget_input.set_job_manager(self.job_manager)

        self.logger = logging.getLogger(__name__)

        # colorize button
        self.ui.pushButton_run.setStyleSheet("""
        QPushButton {
            padding-left: 10px;
            padding-right: 10px;
            padding-top: 10px;
            padding-bottom: 10px;
            qproperty-iconSize: 20px;
            color: white;
            font-weight: bold;
            background-color: #3C41AA;
        }
        QPushButton:hover {
            background-color: #4C51BA;
        }
        QPushButton:pressed {
            background-color: #2C319A;
        }
        """)
        self.ui.pushButton_run.setIcon(get_icon("chipstream_white"))

        # Populate segmenter combobox
        self.ui.comboBox_segmenter.blockSignals(True)
        self.ui.comboBox_segmenter.clear()
        # copy
        self.ui.comboBox_segmenter.addItem("Disabled (from input file)",
                                           "copy")
        # thresh
        self.ui.comboBox_segmenter.addItem("Thresholding", "thresh")
        # torch
        self.ui.comboBox_segmenter.addItem("Machine-learning model", "torch")
        use_gpu = cuda_is_available()
        self.ui.checkBox_torch_use_gpu.setVisible(use_gpu)
        self.ui.checkBox_torch_use_gpu.setChecked(use_gpu)
        available_models = []
        for pdir in dcnum_paths.search_path_registry.get("torch_model_files",
                                                         []):
            available_models += [p for p in pdir.glob("*.dcnm")]
        # Do not show models that the user removed from the list
        removed_models = self.get_removed_torch_models()
        available_models = sorted(
            (p for p in set(available_models)
             if str(p) not in removed_models),
            key=torch_model_sort_key)
        if available_models:
            self.ui.comboBox_torch_model.clear()
            self.ui.comboBox_torch_model.setEnabled(True)
            self.ui.toolButton_torch_info.setEnabled(True)
            self.ui.toolButton_torch_remove.setEnabled(True)
            for mpath in available_models:
                self.ui.comboBox_torch_model.addItem(mpath.stem, mpath)
            default_segmenter = "torch"
        else:
            default_segmenter = "thresh"
        self.ui.toolButton_torch_add.clicked.connect(self.on_torch_model_add)
        self.ui.toolButton_torch_info.clicked.connect(self.on_torch_model_info)
        self.ui.toolButton_torch_remove.clicked.connect(
            self.on_torch_model_remove)

        self.ui.comboBox_segmenter.blockSignals(False)
        self.ui.comboBox_segmenter.setCurrentIndex(
            self.ui.comboBox_segmenter.findData(default_segmenter))

        # Maximum CPU count
        self.ui.spinBox_procs.setMaximum(cpu_count())
        self.ui.spinBox_procs.setValue(cpu_count())

        # GUI
        self.setWindowTitle(f"ChipStream {version}")
        # Disable native menu bar (e.g. on Mac)
        self.ui.menubar.setNativeMenuBar(False)

        # File menu
        self.ui.actionAdd.triggered.connect(self.on_action_add)
        self.ui.actionClear.triggered.connect(self.on_action_clear)
        self.ui.actionQuit.triggered.connect(self.on_action_quit)
        # Settings menu
        self.ui.actionExpertSettings.triggered.connect(
            self.on_action_expert_settings)
        #: Additional keyword arguments for the pipeline steps (lists of
        #: "KEY=VALUE" strings, see `EXPERT_STEPS`), only for this session
        self.expert_kwargs = {key: [] for key, _ in EXPERT_STEPS}
        self.label_expert_warning = QtWidgets.QLabel(
            "\u26a0 Expert settings active (Settings \u2192 Expert settings)")
        self.label_expert_warning.setStyleSheet(
            "QLabel { color: #b35900; font-weight: bold; }")
        self.label_expert_warning.setVisible(False)
        self.ui.statusbar.addWidget(self.label_expert_warning)
        # Help menu
        self.ui.actionDocumentation.triggered.connect(self.on_action_docs)
        self.ui.actionSoftware.triggered.connect(self.on_action_software)
        self.ui.actionAbout.triggered.connect(self.on_action_about)

        # Command button
        self.ui.pushButton_run.clicked.connect(self.on_run)
        self.ui.pushButton_pause.setVisible(False)
        self.ui.pushButton_pause.toggled.connect(self.on_pause)

        # Path selection
        cache_loc = pathlib.Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.CacheLocation))
        cache_loc.mkdir(parents=True, exist_ok=True)
        self.path_cache = PathCache(cache_loc / "output_paths.txt")
        atexit.register(self.path_cache.cleanup)
        self.ui.comboBox_output.clear()
        self.ui.comboBox_output.addItem("Output alongside input files",
                                        "input")
        for ii, path in enumerate(self.path_cache):
            self.ui.comboBox_output.addItem(str(path), ii)
        self.ui.comboBox_output.addItem("Select output directory", "new")
        self.ui.comboBox_output.currentIndexChanged.connect(self.on_path_out)

        # Signals
        self.run_completed.connect(self.on_run_completed)
        self.ui.tableWidget_input.row_selected.connect(self.on_select_job)

        # if "--version" was specified, print the version and exit
        if "--version" in arguments:
            print(version)
            QtWidgets.QApplication.processEvents(
                QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
            sys.exit(0)

        # Create a timer that continuously updates self.ui.textBrowser
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(
            self.ui.tableWidget_input.on_selection_changed)
        self.timer.start(1000)

        # Show the CPU and RAM usage in the status bar
        self.label_sys_usage = SystemUsageLabel(self)
        self.ui.statusbar.addPermanentWidget(self.label_sys_usage)

        splash.splash_close()

        # finalize
        self.show()
        self.activateWindow()
        self.setWindowState(QtCore.Qt.WindowState.WindowActive)

    def append_paths(self, path_list):
        """Add input paths to the table"""
        if not self.job_manager.is_busy():
            for pp in path_list:
                self.job_manager.add_path(pp)
            self.ui.tableWidget_input.update_from_job_manager()

    @QtCore.pyqtSlot(QtCore.QEvent)
    def closeEvent(self, event):
        jobs_running = self.is_running()
        if jobs_running:
            self.job_manager.close(force=True)
        event.accept()
        if jobs_running:
            time.sleep(1)
            # We have killed all background jobs, we might be littered with
            # zombies. Everything is probably broken. Just get rid of
            # ourselves.
            psutil.Process().kill()

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
                pathlist += list(pp.rglob("*.rtdc"))
            elif pp.suffix == ".rtdc":
                pathlist.append(pp)
        self.append_paths(pathlist)

    def get_job_kwargs(self):
        """Return the job keyword arguments, including expert settings"""
        job_kwargs = self.get_job_kwargs_basic()
        self.apply_expert_kwargs(job_kwargs, self.expert_kwargs)
        return job_kwargs

    def get_job_kwargs_basic(self):
        """Return the job keyword arguments defined in the main window"""
        # did the user select a pixel size?
        if self.ui.checkBox_pixel_size.isChecked():
            data_kwargs = {
                "pixel_size": self.ui.doubleSpinBox_pixel_size.value()
            }
        else:
            data_kwargs = None

        # default background computer is "sparsemed"
        bg_default = feat_background.BackgroundSparseMed
        bg_kwargs = dict(inspect.getfullargspec(
            bg_default.check_user_kwargs).kwonlydefaults or {})
        # The job manager detects whether offset correction is necessary
        # for each input file (unless it is set in the expert settings).
        bg_kwargs.pop("offset_correction", None)

        # populate segmenter and its kwargs
        segmenter = self.ui.comboBox_segmenter.currentData()
        segmenter_kwargs = {}
        if segmenter == "thresh":
            segmenter_kwargs["thresh"] = self.ui.spinBox_thresh.value()
        elif segmenter == "torch":
            if self.ui.checkBox_torch_use_gpu.isChecked():
                segmenter = "torchsto"
            else:
                segmenter = "torchmpo"
            segmenter_kwargs["model_file"] = \
                self.ui.comboBox_torch_model.currentData()

        job_kwargs = {
            "data_code": "hdf",
            "data_kwargs": data_kwargs,
            "background_code": bg_default.get_ppid_code(),
            "background_kwargs": bg_kwargs,
            "segmenter_code": segmenter,
            "segmenter_kwargs": segmenter_kwargs,
            "feature_code": "legacy",
            "feature_kwargs": {
                "brightness": self.ui.checkBox_feat_bright.isChecked(),
                "haralick": self.ui.checkBox_feat_haralick.isChecked(),
                "volume": self.ui.checkBox_feat_volume.isChecked(),
                },
            "gate_code": "norm",
            "gate_kwargs": {},
            "basin_strategy":
                "tap" if self.ui.checkBox_basins.isChecked() else "drain",
            "num_procs": self.ui.spinBox_procs.value(),
        }

        return job_kwargs

    @staticmethod
    def apply_expert_kwargs(job_kwargs: dict,
                            expert_kwargs: dict[str, list[str]]):
        """Update `job_kwargs` in-place with the expert keyword arguments

        Raises
        ------
        kwargs_parse.KeywordArgumentError
            if the expert keyword arguments are invalid (e.g. for the
            selected segmenter)
        """
        bg_code = job_kwargs["background_code"]
        job_kwargs["background_kwargs"].update(
            kwargs_parse.parse_background_kwargs(
                bg_code, expert_kwargs.get("background"),
                option="background"))
        seg_args = expert_kwargs.get("segmentation")
        if seg_args:
            seg_code = job_kwargs["segmenter_code"]
            if seg_code not in kwargs_parse.get_segmenters():
                raise kwargs_parse.KeywordArgumentError(
                    f"The segmenter '{seg_code}' does not accept keyword "
                    f"arguments", option="segmentation")
            seg_kwargs = kwargs_parse.parse_segmentation_kwargs(
                seg_code, seg_args, option="segmentation")
            kwargs_mask = seg_kwargs.pop("kwargs_mask")
            job_kwargs["segmenter_kwargs"].update(seg_kwargs)
            if kwargs_mask:
                job_kwargs["segmenter_kwargs"].setdefault(
                    "kwargs_mask", {}).update(kwargs_mask)
        job_kwargs["feature_kwargs"].update(
            kwargs_parse.parse_feature_kwargs(
                expert_kwargs.get("feature"), option="feature extraction"))
        job_kwargs["gate_kwargs"].update(
            kwargs_parse.parse_gate_kwargs(
                expert_kwargs.get("gate"), option="gating"))

    def is_running(self):
        return self.job_manager.is_busy()

    @QtCore.pyqtSlot()
    def on_action_expert_settings(self):
        """Let the user edit additional keyword arguments"""
        def validator(expert_kwargs):
            self.apply_expert_kwargs(self.get_job_kwargs_basic(),
                                     expert_kwargs)

        dlg = ExpertSettingsDialog(self, self.expert_kwargs, validator)
        if dlg.exec():
            self.set_expert_kwargs(dlg.get_expert_kwargs())

    def set_expert_kwargs(self, expert_kwargs: dict[str, list[str]]):
        """Set the expert keyword arguments and show/hide the warning"""
        self.expert_kwargs = {key: list(expert_kwargs.get(key, []))
                              for key, _ in EXPERT_STEPS}
        active = [f"{key}: {', '.join(args)}"
                  for key, args in self.expert_kwargs.items() if args]
        self.label_expert_warning.setVisible(bool(active))
        self.label_expert_warning.setToolTip("\n".join(active))

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
                      f"<a href='https://{rtd}'>{rtd}</a><br>")
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
        self.job_manager.clear()
        self.ui.tableWidget_input.update_from_job_manager()

    @QtCore.pyqtSlot()
    def on_action_docs(self):
        webbrowser.open("https://chipstream.readthedocs.io")

    @QtCore.pyqtSlot()
    def on_action_software(self) -> None:
        """Show used software packages and dependencies."""
        libs = ["dcnum",
                "h5py",
                "hdf5plugin",
                "mahotas",
                "numba",
                "numpy",
                "psutil",
                "scipy",
                "torch"
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
                if hasattr(mod, "__version__"):
                    mversion = mod.__version__
                elif hasattr(mod, "_version"):
                    mversion = mod._version.version
                else:
                    mversion = ""

                sw_text += f"- {mod.__name__} {mversion}\n"
        sw_text += f"- PyQt6 {QtCore.QT_VERSION_STR}\n"

        QtWidgets.QMessageBox.information(self, "Software", sw_text)

    @QtCore.pyqtSlot()
    def on_action_quit(self) -> None:
        """Determine what happens when the user wants to quit"""
        QtCore.QCoreApplication.quit()

    @QtCore.pyqtSlot()
    def on_path_out(self):
        data = self.ui.comboBox_output.currentData()
        if data == "input":
            # Store output data alongside input data
            self.job_manager.set_output_path(None)
        elif data == "new":
            # New output path
            default = "." if len(self.path_cache) == 0 else self.path_cache[-1]
            # Open a directory selection dialog
            path = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                "Choose data output directory",
                str(default),
            )
            self.ui.comboBox_output.blockSignals(True)
            if path and pathlib.Path(path).exists():
                self.ui.comboBox_output.insertItem(
                    len(self.path_cache) + 1,  # index in combobox
                    path,
                    len(self.path_cache),  # user data == index in path_cache
                    )
                self.ui.comboBox_output.setCurrentIndex(
                    len(self.path_cache) + 1)
                self.path_cache.add_path(pathlib.Path(path))
                self.job_manager.set_output_path(path)
            else:
                # User pressed cancel
                self.ui.comboBox_output.setCurrentIndex(0)
                self.job_manager.set_output_path(None)
            self.ui.comboBox_output.blockSignals(False)
        else:
            # Data is an integer index for `self.path_cache`
            self.job_manager.set_output_path(self.path_cache[data])

    @QtCore.pyqtSlot()
    def on_run(self):
        """Run the analysis"""
        # When we start running, we disable all the controls until we are
        # finished. The user can still add items to the list but not
        # change the pipeline.
        try:
            job_kwargs = self.get_job_kwargs()
        except kwargs_parse.KeywordArgumentError as e:
            QtWidgets.QMessageBox.critical(
                self, "Invalid expert settings",
                f"The expert settings are invalid for the selected "
                f"pipeline ({e.option}): {e}")
            return
        self.set_options_enabled(False)
        self.job_manager.run_all_in_thread(
            job_kwargs=job_kwargs,
            callback_when_done=self.run_completed.emit)

    @QtCore.pyqtSlot(bool)
    def on_pause(self, pause):
        """Pause or resume the analysis"""
        if pause:
            self.job_manager.pause()
            self.ui.pushButton_pause.setText("Resume")
        else:
            self.job_manager.resume()
            self.ui.pushButton_pause.setText("Pause")

    @QtCore.pyqtSlot()
    def on_run_completed(self):
        self.set_options_enabled(True)

    def set_options_enabled(self, enabled: bool):
        """Enable the pipeline options (disabled while running)

        While the pipeline is running, the options and the "Run"
        button are disabled and the "Pause" button is shown.
        """
        for widget in [self.ui.groupBox_4,
                       self.ui.groupBox_5,
                       self.ui.groupBox_6,
                       self.ui.pushButton_run]:
            widget.setEnabled(enabled)
        if enabled:
            # make sure nothing stays suspended
            self.ui.pushButton_pause.setChecked(False)
        self.ui.pushButton_pause.setVisible(not enabled)

    @QtCore.pyqtSlot(int)
    def on_select_job(self, row):
        if row < 0:
            info = "No job selected."
        else:
            # Display some information in the lower text box.
            info = self.job_manager.get_info(row)
        # Compare the text to the current text.
        old_text = self.ui.textBrowser.toPlainText()
        if info != old_text:
            sb = self.ui.textBrowser.verticalScrollBar()
            is_at_end = sb is not None and sb.maximum() - sb.value() <= 10
            self.ui.textBrowser.setText(info)
            if (sb is not None
                    and info.strip().startswith(old_text.strip())
                    and is_at_end):
                # Automatically scroll to the bottom
                sb.setValue(sb.maximum())

    @QtCore.pyqtSlot()
    def on_torch_model_add(self):
        """Ask the user for a path to a .dcnm file and remember it"""
        pathlist, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            'Select segmentation model files',
            '',
            'Model files (*.dcnm)')
        cur_mod_paths = self.settings.value("segm/torch_model_files", [])
        removed_models = self.get_removed_torch_models()
        for path in pathlist:
            path = pathlib.Path(path)
            dcnum_paths.register_search_path("torch_model_files",
                                             path.parent)
            cur_mod_paths.append(str(path.parent))
            # A model that was removed earlier is shown again
            removed_models.discard(str(path))
            if not self.ui.comboBox_torch_model.isEnabled():
                self.ui.comboBox_torch_model.clear()
            cb = self.ui.comboBox_torch_model
            # `findData` does not compare `pathlib.Path` objects by value
            paths = [cb.itemData(ii) for ii in range(cb.count())]
            if path not in paths:
                # Insert the model at its sorted position
                key = torch_model_sort_key(path)
                for idx, other in enumerate(paths):
                    if (other is not None
                            and key < torch_model_sort_key(other)):
                        cb.insertItem(idx, path.stem, path)
                        break
                else:
                    cb.addItem(path.stem, path)
            self.ui.comboBox_torch_model.setEnabled(True)
            self.ui.toolButton_torch_info.setEnabled(True)
            self.ui.toolButton_torch_remove.setEnabled(True)
        cur_mod_paths = sorted(set(cur_mod_paths))
        if cur_mod_paths:
            self.settings.setValue("segm/torch_model_files", cur_mod_paths)
        self.set_removed_torch_models(removed_models)

    @QtCore.pyqtSlot()
    def on_torch_model_remove(self):
        """Remove the selected model from the list of models

        The model file is not deleted. Since the directories of the
        model files are remembered (and all models in them are listed),
        the removed model is stored in the settings, so that it is not
        listed in the next session. Adding the model again with
        :func:`on_torch_model_add` lists it again.
        """
        idx = self.ui.comboBox_torch_model.currentIndex()
        path = self.ui.comboBox_torch_model.currentData()
        if idx < 0 or path is None:
            return
        self.ui.comboBox_torch_model.removeItem(idx)
        removed_models = self.get_removed_torch_models()
        removed_models.add(str(path))
        self.set_removed_torch_models(removed_models)
        if self.ui.comboBox_torch_model.count() == 0:
            self.ui.comboBox_torch_model.addItem("No models available")
            self.ui.comboBox_torch_model.setEnabled(False)
            self.ui.toolButton_torch_info.setEnabled(False)
            self.ui.toolButton_torch_remove.setEnabled(False)

    def get_removed_torch_models(self) -> set[str]:
        """Return the paths of the models the user removed from the list"""
        return set(self.settings.value("segm/torch_model_files_removed", [],
                                       type=list))

    def set_removed_torch_models(self, removed_models: set[str]):
        """Store the paths of the models the user removed from the list"""
        if removed_models:
            self.settings.setValue("segm/torch_model_files_removed",
                                   sorted(removed_models))
        else:
            self.settings.remove("segm/torch_model_files_removed")

    @QtCore.pyqtSlot()
    def on_torch_model_info(self):
        """Show the user model-related information"""
        model_file = self.ui.comboBox_torch_model.currentData()
        dlg = TorchModelProperties(self, model_file)
        dlg.exec()


def torch_model_sort_key(path: pathlib.Path) -> tuple:
    """Key for sorting model files by name (case-insensitive, natural)

    Numbers in the file name are compared by value, so that e.g.
    "model_2" comes before "model_10". The full path is used for
    sorting models with the same name.
    """
    parts = re.split(r"(\d+)", pathlib.Path(path).stem.lower())
    name_key = [(0, int(pp), "") if pp.isdigit() else (1, 0, pp)
                for pp in parts if pp]
    return name_key, str(path)


@functools.lru_cache(maxsize=100)
def get_icon(name):
    try:
        icon = QtGui.QIcon()
        ref = importlib.resources.files(
            "chipstream.gui.img") / f"{name}.svg"
        with importlib.resources.as_file(ref) as path:
            icon.addFile(str(path))
        if name != "placeholder" and icon.isNull():
            icon = get_icon("placeholder")
    except BaseException:
        if name == "placeholder":
            raise
        else:
            icon = get_icon("placeholder")
    return icon


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
        main.logger.error(exception)
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


def get_main() -> ChipStream:
    app = QtWidgets.QApplication.instance()
    for widget in app.topLevelWidgets():
        if isinstance(widget, ChipStream):
            return widget
    raise ValueError("Main instance not found!")


# Make Ctr+C close the app
signal.signal(signal.SIGINT, signal.SIG_DFL)
# Display exception hook in separate dialog instead of crashing
sys.excepthook = excepthook
