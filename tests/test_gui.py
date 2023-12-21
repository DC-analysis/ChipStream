import time

import pytest

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
