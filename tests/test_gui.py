import os
import pathlib
import re
import shutil
import sys
import time
import types

import dcnum.read
import h5py
import numpy as np
import pytest

from helper_methods import retrieve_data, retrieve_model

# https://github.com/pytorch/pytorch/issues/166628
# Import pytorch before PyQt6
try:
    import torch  # noqa: F401
except ImportError:
    pass

pytest.importorskip("PyQt6")

from PyQt6 import QtCore, QtWidgets, QtTest  # noqa: E402

from chipstream.gui.main_window import ChipStream  # noqa: E402


@pytest.fixture
def mw(qtbot):
    # Code that will run before your test
    mw = ChipStream()
    qtbot.addWidget(mw)
    QtWidgets.QApplication.setActiveWindow(mw)
    QtTest.QTest.qWait(100)
    QtWidgets.QApplication.processEvents(
        QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
    # disable GPU for tests
    mw.ui.checkBox_torch_use_gpu.setChecked(False)
    # Run test
    yield mw
    # Make sure that all daemons are gone
    mw.close()
    # It is extremely weird, but this seems to be important to avoid segfaults!
    time.sleep(1)
    QtTest.QTest.qWait(100)
    QtWidgets.QApplication.processEvents(
        QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)


def test_gui_basic(mw):
    # Just check some known properties in the UI.
    assert mw.ui.spinBox_thresh.value() == -6
    assert mw.ui.checkBox_feat_bright.isChecked()
    assert len(mw.job_manager) == 0


@pytest.mark.parametrize("use_basins", [True, False])
def test_gui_basins(mw, use_basins):
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    mw.append_paths([path])
    mw.ui.checkBox_basins.setChecked(use_basins)
    mw.on_run()
    while mw.job_manager.is_busy():
        time.sleep(.1)
    out_path = path.with_name(path.stem + "_dcn.rtdc")
    assert out_path.exists()

    with h5py.File(out_path) as h5:
        for feat in ["image", "frame"]:
            if not use_basins:
                assert feat in h5["events"]
            else:
                assert feat not in h5["events"]
        for feat in ["mask", "deform", "aspect"]:
            assert feat in h5["events"]


@pytest.mark.parametrize("add_flickering", [True, False])
def test_gui_correct_offset(mw, add_flickering):
    """Offset correction is done automatically"""
    path_temp = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    path = path_temp.with_name("input_path.rtdc")

    # create a test file for more than 100 events
    with dcnum.read.concatenated_hdf5_data(
        paths=3*[path_temp],
        path_out=path,
            compute_frame=True):
        pass

    if add_flickering:
        # provoke offset correction in CLI
        with h5py.File(path, "a") as h5:
            size = len(h5["events/image"])
            images_orig = h5["events/image"]
            del h5["events/image"]
            offset = np.zeros((size, 1, 1), dtype=np.uint8)
            # add flickering every five frames
            offset[::5] += 5
            h5["events/image"] = np.array(
                images_orig + offset,
                dtype=np.uint8
            )
    mw.append_paths([path])
    mw.ui.checkBox_pixel_size.setChecked(True)
    mw.ui.doubleSpinBox_pixel_size.setValue(0.666)
    mw.on_run()
    while mw.job_manager.is_busy():
        time.sleep(.1)
    out_path = path.with_name(path.stem + "_dcn.rtdc")
    assert out_path.exists()

    with h5py.File(out_path) as h5:
        assert np.allclose(h5.attrs["imaging:pixel size"],
                           0.666,
                           atol=0, rtol=1e-5)
        if add_flickering:
            assert h5.attrs["pipeline:dcnum background"] \
                   == "sparsemed:k=200^s=1^t=0^f=0.8^o=1"
            assert "bg_off" in h5["events"]
        else:
            assert h5.attrs["pipeline:dcnum background"] \
                   == "sparsemed:k=200^s=1^t=0^f=0.8^o=0"
            assert "bg_off" not in h5["events"]


def test_gui_segm_torch_model(mw, qtbot, monkeypatch):
    pytest.importorskip("torch")
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    path_model = retrieve_model(
        "segm-torch-model_unet-dcnum-test_g1_910c2.zip")

    # Import the model
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileNames",
                        lambda *args: ([path_model], ""))
    qtbot.mouseClick(mw.ui.toolButton_torch_add,
                     QtCore.Qt.MouseButton.LeftButton)
    # select the model
    for idm in range(mw.ui.comboBox_torch_model.count()):
        data = mw.ui.comboBox_torch_model.itemData(idm)
        if data.name == path_model.name:
            break
    else:
        assert False

    mw.ui.comboBox_torch_model.setCurrentIndex(idm)

    # Add the input file
    mw.append_paths([path])

    # Run the analysis
    mw.on_run()
    while mw.job_manager.is_busy():
        time.sleep(.1)
    out_path = path.with_name(path.stem + "_dcn.rtdc")
    assert out_path.exists()

    with h5py.File(out_path) as h5:
        # test feature availability
        for feat in ["mask", "deform", "aspect"]:
            assert feat in h5["events"]
        # test metadata
        assert h5.attrs["pipeline:dcnum segmenter"] \
               == f"torchmpo:m={path_model.name}:cle=1^f=1^clo=0"


def test_gui_segm_torch_model_remove(mw, qtbot, monkeypatch):
    """Remove a model from the list; it is not listed in a new session"""
    path_model = retrieve_model(
        "segm-torch-model_unet-dcnum-test_g1_910c2.zip")
    key = "segm/torch_model_files_removed"
    removed_orig = mw.settings.value(key, [], type=list)

    def model_paths(window):
        # Compare full paths: other tests may have added models with
        # the same name from other directories.
        cb = window.ui.comboBox_torch_model
        return [pathlib.Path(cb.itemData(ii)) for ii in range(cb.count())
                if cb.itemData(ii) is not None]

    try:
        monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileNames",
                            lambda *args: ([str(path_model)], ""))
        # adding the same model twice lists it once
        for _ in range(2):
            qtbot.mouseClick(mw.ui.toolButton_torch_add,
                             QtCore.Qt.MouseButton.LeftButton)
        assert model_paths(mw).count(path_model) == 1
        assert mw.ui.toolButton_torch_remove.isEnabled()

        # select and remove the model
        cb = mw.ui.comboBox_torch_model
        cb.setCurrentIndex(model_paths(mw).index(path_model))
        qtbot.mouseClick(mw.ui.toolButton_torch_remove,
                         QtCore.Qt.MouseButton.LeftButton)
        assert path_model not in model_paths(mw)
        assert str(path_model) in mw.get_removed_torch_models()
        assert path_model.exists(), "the model file must not be deleted"

        # the model is not listed in a new session
        mw2 = ChipStream()
        qtbot.addWidget(mw2)
        assert path_model not in model_paths(mw2)
        mw2.close()

        # adding the model again lists it again
        qtbot.mouseClick(mw.ui.toolButton_torch_add,
                         QtCore.Qt.MouseButton.LeftButton)
        assert model_paths(mw).count(path_model) == 1
        assert str(path_model) not in mw.get_removed_torch_models()
    finally:
        mw.set_removed_torch_models(set(removed_orig))


def test_gui_segm_torch_model_with_wrong_model(mw, qtbot, monkeypatch):
    pytest.importorskip("torch")
    # Create a test dataset with metadata that will make the model invalid
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")

    with h5py.File(path, "a") as h5:
        h5.attrs["setup:chip region"] = "reservoir"

    path_model = retrieve_model(
        "segm-torch-model_unet-dcnum-test_g1_910c2.zip")

    # Import the model
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileNames",
                        lambda *args: ([path_model], ""))
    qtbot.mouseClick(mw.ui.toolButton_torch_add,
                     QtCore.Qt.MouseButton.LeftButton)
    # select the model
    for idm in range(mw.ui.comboBox_torch_model.count()):
        data = mw.ui.comboBox_torch_model.itemData(idm)
        if data.name == path_model.name:
            break
    else:
        assert False

    mw.ui.comboBox_torch_model.setCurrentIndex(idm)

    # Add the input file
    mw.append_paths([path])

    # Run the analysis
    mw.on_run()
    while mw.job_manager.is_busy():
        time.sleep(.1)
    out_path = path.with_name(path.stem + "_dcn.rtdc")
    assert not out_path.exists()

    # Make sure there is an error message in the interface
    qtbot.mouseClick(mw.ui.tableWidget_input.cellWidget(0, 2),
                     QtCore.Qt.MouseButton.LeftButton)
    assert mw.ui.textBrowser.toPlainText().count(
        "only experiments in channel region supported")


def test_gui_set_pixel_size(mw):
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    mw.append_paths([path])
    mw.ui.checkBox_pixel_size.setChecked(True)
    mw.ui.doubleSpinBox_pixel_size.setValue(0.666)
    mw.on_run()
    while mw.job_manager.is_busy():
        time.sleep(.1)
    out_path = path.with_name(path.stem + "_dcn.rtdc")
    assert out_path.exists()

    with h5py.File(out_path) as h5:
        assert np.allclose(h5.attrs["imaging:pixel size"],
                           0.666,
                           atol=0, rtol=1e-5)


@pytest.mark.parametrize("use_volume", [True, False])
def test_gui_use_volume(mw, use_volume):
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    mw.append_paths([path])
    mw.ui.checkBox_pixel_size.setChecked(True)
    mw.ui.checkBox_feat_volume.setChecked(use_volume)
    mw.ui.doubleSpinBox_pixel_size.setValue(0.666)
    mw.on_run()
    while mw.job_manager.is_busy():
        time.sleep(.1)
    out_path = path.with_name(path.stem + "_dcn.rtdc")
    assert out_path.exists()

    with h5py.File(out_path) as h5:
        assert np.allclose(h5.attrs["imaging:pixel size"],
                           0.666,
                           atol=0, rtol=1e-5)
        assert ("volume" in h5["events"]) == use_volume


def test_gui_sys_usage(mw):
    """CPU and RAM usage are shown in the status bar"""
    label = mw.label_sys_usage
    assert label in mw.ui.statusbar.findChildren(QtWidgets.QLabel)
    assert label.timer.isActive()
    label.update_usage()
    text = label.text()
    # (the GPU usage is only shown if an NVIDIA GPU is available)
    assert re.match(r"CPU \d+%   RAM \d+\.\d / \d+\.\d GiB \(\d+%\)"
                    r"(   GPU.*)?$", text), text


class FakeNVML:
    """Fake `pynvml` module"""
    class NVMLError(Exception):
        pass

    def __init__(self, num_gpus=1, fail=False, memory_v2=False):
        self.num_gpus = num_gpus
        self.fail = fail
        if memory_v2:
            self.nvmlMemory_v2 = 2

    def nvmlInit(self):
        pass

    def nvmlDeviceGetCount(self):
        return self.num_gpus

    def nvmlDeviceGetHandleByIndex(self, index):
        return index

    def nvmlDeviceGetUtilizationRates(self, handle):
        if self.fail:
            raise self.NVMLError("GPU is lost")
        return types.SimpleNamespace(gpu=45 + 10 * handle, memory=3)

    def nvmlDeviceGetMemoryInfo(self, handle, version=None):
        # version 2 does not count memory reserved by the driver as used
        reserved = 0.5 if version == 2 else 0
        return types.SimpleNamespace(
            used=(2 + handle - reserved) * 1024**3,
            total=4 * 1024**3,
            free=(2 - handle) * 1024**3)


@pytest.mark.parametrize("num_gpus,memory_v2,expected", [
    [1, False, "   GPU 45% 2.0 / 4.0 GiB"],
    [2, False, "   GPU0 45% 2.0 / 4.0 GiB   GPU1 55% 3.0 / 4.0 GiB"],
    # memory info version 2 (as shown by `nvidia-smi`)
    [1, True, "   GPU 45% 1.5 / 4.0 GiB"],
])
def test_gui_sys_usage_gpu(qtbot, monkeypatch, num_gpus, memory_v2, expected):
    """The NVIDIA GPU usage is shown if available"""
    from chipstream.gui import sys_usage
    monkeypatch.setitem(sys.modules, "pynvml",
                        FakeNVML(num_gpus=num_gpus, memory_v2=memory_v2))
    label = sys_usage.SystemUsageLabel()
    qtbot.addWidget(label)
    assert label.text().endswith(expected), label.text()
    assert label.text().startswith("CPU ")


def test_gui_sys_usage_gpu_error(qtbot, monkeypatch):
    """Errors when reading the GPU usage hide the GPU usage"""
    from chipstream.gui import sys_usage
    monkeypatch.setitem(sys.modules, "pynvml", FakeNVML(fail=True))
    label = sys_usage.SystemUsageLabel()
    qtbot.addWidget(label)
    assert label.gpu_handles
    assert "GPU" not in label.text()


def test_gui_sys_usage_no_nvml(qtbot, monkeypatch):
    """Without nvidia-ml-py, the GPU usage is not shown"""
    from chipstream.gui import sys_usage
    # `import pynvml` raises ImportError if the module entry is None
    monkeypatch.setitem(sys.modules, "pynvml", None)
    label = sys_usage.SystemUsageLabel()
    qtbot.addWidget(label)
    assert label.nvml is None
    assert "GPU" not in label.text()


def test_gui_expert_kwargs_job_kwargs(mw):
    """Expert keyword arguments end up in the job keyword arguments"""
    mw.ui.comboBox_segmenter.setCurrentIndex(
        mw.ui.comboBox_segmenter.findData("thresh"))
    assert not mw.label_expert_warning.isVisibleTo(mw)
    mw.set_expert_kwargs({
        "background": ["kernel_size=150", "offset_correction=false"],
        "segmentation": ["thresh=-4", "closing_disk=3"],
        "feature": ["haralick=False"],
        "gate": ["size_thresh_mask=5"],
    })
    assert mw.label_expert_warning.isVisibleTo(mw)
    assert mw.label_expert_warning.toolTip().count("thresh=-4")

    job_kwargs = mw.get_job_kwargs()
    assert job_kwargs["background_kwargs"]["kernel_size"] == 150
    assert job_kwargs["background_kwargs"]["offset_correction"] is False
    # expert settings override the settings in the main window
    assert job_kwargs["segmenter_kwargs"]["thresh"] == -4
    assert job_kwargs["segmenter_kwargs"]["kwargs_mask"] == {
        "closing_disk": 3}
    assert job_kwargs["feature_kwargs"]["haralick"] is False
    assert job_kwargs["gate_kwargs"] == {"size_thresh_mask": 5}

    # removing all expert settings hides the warning
    mw.set_expert_kwargs({})
    assert not mw.label_expert_warning.isVisibleTo(mw)
    job_kwargs = mw.get_job_kwargs()
    assert "offset_correction" not in job_kwargs["background_kwargs"]
    assert job_kwargs["gate_kwargs"] == {}


def test_gui_expert_kwargs_invalid(mw, monkeypatch):
    """Invalid expert settings for the selected segmenter prevent a run"""
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    mw.append_paths([path])
    mw.ui.comboBox_segmenter.setCurrentIndex(
        mw.ui.comboBox_segmenter.findData("thresh"))
    # valid for the torch segmenters, but not for thresholding
    mw.set_expert_kwargs({"segmentation": ["model_file=model.dcnm"]})
    messages = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "critical",
                        lambda *args: messages.append(args[2]))
    mw.on_run()
    assert len(messages) == 1
    assert messages[0].count("Invalid keyword 'model_file' for 'thresh'")
    assert not mw.job_manager.is_busy()
    assert mw.ui.pushButton_run.isEnabled()


def test_gui_expert_kwargs_dialog(mw, monkeypatch):
    """The dialog validates the keyword arguments when OK is clicked"""
    from chipstream.gui.dlg_expert import ExpertSettingsDialog
    mw.ui.comboBox_segmenter.setCurrentIndex(
        mw.ui.comboBox_segmenter.findData("thresh"))
    warnings = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning",
                        lambda *args: warnings.append(args[2]))

    def validator(expert_kwargs):
        mw.apply_expert_kwargs(mw.get_job_kwargs_basic(), expert_kwargs)

    dlg = ExpertSettingsDialog(mw, {"gate": ["size_thresh_mask=5"]},
                               validator)
    assert dlg.edits["gate"].toPlainText() == "size_thresh_mask=5"
    # invalid value: the dialog stays open
    dlg.edits["segmentation"].setPlainText("thresh=abc")
    dlg.accept()
    assert dlg.result() != QtWidgets.QDialog.DialogCode.Accepted
    assert warnings[0].count("Invalid value 'abc' for keyword 'thresh'")
    # valid values (empty lines and comments are ignored)
    dlg.edits["segmentation"].setPlainText("# comment\n\nthresh=-3\n")
    dlg.accept()
    assert dlg.result() == QtWidgets.QDialog.DialogCode.Accepted
    assert dlg.get_expert_kwargs() == {
        "background": [],
        "segmentation": ["thresh=-3"],
        "feature": [],
        "gate": ["size_thresh_mask=5"],
    }


def test_gui_expert_kwargs_run(mw):
    """The expert settings are used in the pipeline"""
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    mw.append_paths([path])
    mw.ui.comboBox_segmenter.setCurrentIndex(
        mw.ui.comboBox_segmenter.findData("thresh"))
    mw.set_expert_kwargs({
        "background": ["offset_correction=true"],
        "segmentation": ["thresh=-4", "closing_disk=3"],
        "feature": ["haralick=False"],
    })
    mw.on_run()
    while mw.job_manager.is_busy():
        time.sleep(.1)
    out_path = path.with_name(path.stem + "_dcn.rtdc")
    with h5py.File(out_path) as h5:
        assert h5.attrs["pipeline:dcnum background"].endswith("^o=1")
        assert h5.attrs["pipeline:dcnum segmenter"] \
            == "thresh:t=-4:cle=1^f=1^clo=3"
        assert h5.attrs["pipeline:dcnum feature"] == "legacy:b=1^h=0^v=1"


def test_gui_segm_torch_models_sorted(mw, qtbot, monkeypatch, tmp_path):
    """The model list is sorted by name (case-insensitive, natural)"""
    path_model = retrieve_model(
        "segm-torch-model_unet-dcnum-test_g1_910c2.zip")
    # dcnum requires the file name to end with the beginning of the MD5
    # sum of the model file ("910c2.dcnm").
    names = ["model_10", "Model_2", "beta", "Alpha", "model_1"]
    paths = []
    for name in names:
        pp = tmp_path / f"{name}_910c2.dcnm"
        shutil.copy2(path_model, pp)
        paths.append(pp)

    def listed_names(window):
        cb = window.ui.comboBox_torch_model
        return [pathlib.Path(cb.itemData(ii)).stem
                for ii in range(cb.count())
                if cb.itemData(ii) is not None
                and pathlib.Path(cb.itemData(ii)).parent == tmp_path]

    expected = [f"{name}_910c2" for name in
                ["Alpha", "beta", "model_1", "Model_2", "model_10"]]
    # Do not keep the temporary model directory in the user settings
    key = "segm/torch_model_files"
    model_dirs_orig = mw.settings.value(key, [], type=list)
    try:
        # add the models one by one in unsorted order
        for pp in paths:
            monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileNames",
                                lambda *args, pp=pp: ([str(pp)], ""))
            qtbot.mouseClick(mw.ui.toolButton_torch_add,
                             QtCore.Qt.MouseButton.LeftButton)
        assert listed_names(mw) == expected

        # the list is also sorted in a new session
        mw2 = ChipStream()
        qtbot.addWidget(mw2)
        assert listed_names(mw2) == expected
        mw2.close()
    finally:
        mw.settings.setValue(key, model_dirs_orig)


def test_gui_pause_button(mw, qtbot):
    """The pause button is shown while running and pauses the jobs"""
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    mw.append_paths([path])
    # do not depend on the models that other tests added
    mw.ui.comboBox_segmenter.setCurrentIndex(
        mw.ui.comboBox_segmenter.findData("thresh"))
    assert not mw.ui.pushButton_pause.isVisibleTo(mw)
    mw.on_run()
    assert mw.ui.pushButton_pause.isVisibleTo(mw)
    assert not mw.ui.pushButton_run.isEnabled()
    assert not mw.ui.groupBox_4.isEnabled()

    qtbot.mouseClick(mw.ui.pushButton_pause,
                     QtCore.Qt.MouseButton.LeftButton)
    try:
        assert mw.job_manager.is_paused()
        assert mw.ui.pushButton_pause.text() == "Resume"
    finally:
        qtbot.mouseClick(mw.ui.pushButton_pause,
                         QtCore.Qt.MouseButton.LeftButton)
    assert not mw.job_manager.is_paused()
    assert mw.ui.pushButton_pause.text() == "Pause"

    while mw.job_manager.is_busy():
        time.sleep(.1)
    qtbot.waitUntil(lambda: mw.ui.pushButton_run.isEnabled(), timeout=5000)
    assert not mw.ui.pushButton_pause.isVisibleTo(mw)
    assert mw.ui.groupBox_4.isEnabled()
    assert path.with_name(path.stem + "_dcn.rtdc").exists(), \
        mw.job_manager.get_info(0)


def test_gui_splash_close_no_workaround(monkeypatch):
    """The PyInstaller splash workaround (`_PYIBoot_SPLASH`) is not needed

    Since PyInstaller 6.10, child processes started with multiprocessing
    do not show the splash screen again (pyinstaller/pyinstaller#8634).
    """
    from chipstream.gui import splash
    monkeypatch.delenv("_PYIBoot_SPLASH", raising=False)
    splash.splash_close()
    assert "_PYIBoot_SPLASH" not in os.environ
