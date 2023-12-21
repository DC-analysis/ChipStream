import pathlib
import shutil
import tempfile
import time
from unittest import mock
import uuid

import pytest

pytest.importorskip("PyQt6")

from PyQt6 import QtCore, QtWidgets, QtTest
from PyQt6.QtWidgets import QInputDialog, QMessageBox

from chipstream.gui.main_window import ChipStream


@pytest.fixture
def mw(qtbot):
    # Always set server correctly, because there is a test that
    # makes sure DCOR-Aid starts with a wrong server.
    QtCore.QCoreApplication.setOrganizationName("DC-Analysis")
    QtCore.QCoreApplication.setOrganizationDomain("mpl.mpg.de")
    QtCore.QCoreApplication.setApplicationName("ChipStream")
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
    settings = QtCore.QSettings()
    QtTest.QTest.qWait(100)
    QtWidgets.QApplication.processEvents(
        QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
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
