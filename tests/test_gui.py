import time

import dcnum.read
import h5py
import numpy as np
import pytest

from helper_methods import retrieve_data, retrieve_model

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
    assert mw.spinBox_thresh.value() == -6
    assert mw.checkBox_feat_bright.isChecked()
    assert len(mw.job_manager) == 0


@pytest.mark.parametrize("use_basins", [True, False])
def test_gui_basins(mw, use_basins):
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    mw.append_paths([path])
    mw.checkBox_basins.setChecked(use_basins)
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
    mw.checkBox_pixel_size.setChecked(True)
    mw.doubleSpinBox_pixel_size.setValue(0.666)
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
    qtbot.mouseClick(mw.toolButton_torch_add, QtCore.Qt.MouseButton.LeftButton)
    # select the model
    for idm in range(mw.comboBox_torch_model.count()):
        data = mw.comboBox_torch_model.itemData(idm)
        if data.name == path_model.name:
            break
    else:
        assert False

    mw.comboBox_torch_model.setCurrentIndex(idm)

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
    qtbot.mouseClick(mw.toolButton_torch_add, QtCore.Qt.MouseButton.LeftButton)
    # select the model
    for idm in range(mw.comboBox_torch_model.count()):
        data = mw.comboBox_torch_model.itemData(idm)
        if data.name == path_model.name:
            break
    else:
        assert False

    mw.comboBox_torch_model.setCurrentIndex(idm)

    # Add the input file
    mw.append_paths([path])

    # Run the analysis
    mw.on_run()
    while mw.job_manager.is_busy():
        time.sleep(.1)
    out_path = path.with_name(path.stem + "_dcn.rtdc")
    assert not out_path.exists()

    # Make sure there is an error message in the interface
    qtbot.mouseClick(mw.tableWidget_input.cellWidget(0, 2),
                     QtCore.Qt.MouseButton.LeftButton)
    assert mw.textBrowser.toPlainText().count(
        "only experiments in channel region supported")


def test_gui_set_pixel_size(mw):
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    mw.append_paths([path])
    mw.checkBox_pixel_size.setChecked(True)
    mw.doubleSpinBox_pixel_size.setValue(0.666)
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
    mw.checkBox_pixel_size.setChecked(True)
    mw.checkBox_feat_volume.setChecked(use_volume)
    mw.doubleSpinBox_pixel_size.setValue(0.666)
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
