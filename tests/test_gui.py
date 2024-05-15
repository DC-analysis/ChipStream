import time

import h5py
import numpy as np
import pytest

from helper_methods import retrieve_data

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
    assert len(mw.manager) == 0


@pytest.mark.parametrize("correct_offset", [True, False])
def test_gui_correct_offset(mw, correct_offset):
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    mw.append_paths([path])
    mw.checkBox_pixel_size.setChecked(True)
    mw.checkBox_bg_flickering.setChecked(correct_offset)
    mw.doubleSpinBox_pixel_size.setValue(0.666)
    mw.on_run()
    while mw.manager.is_busy():
        time.sleep(.1)
    out_path = path.with_name(path.stem + "_dcn.rtdc")
    assert out_path.exists()

    with h5py.File(out_path) as h5:
        assert np.allclose(h5.attrs["imaging:pixel size"],
                           0.666,
                           atol=0, rtol=1e-5)
        assert ("bg_off" in h5["events"]) == correct_offset


def test_gui_set_pixel_size(mw):
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    mw.append_paths([path])
    mw.checkBox_pixel_size.setChecked(True)
    mw.doubleSpinBox_pixel_size.setValue(0.666)
    mw.on_run()
    while mw.manager.is_busy():
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
    while mw.manager.is_busy():
        time.sleep(.1)
    out_path = path.with_name(path.stem + "_dcn.rtdc")
    assert out_path.exists()

    with h5py.File(out_path) as h5:
        assert np.allclose(h5.attrs["imaging:pixel size"],
                           0.666,
                           atol=0, rtol=1e-5)
        assert ("volume" in h5["events"]) == use_volume
