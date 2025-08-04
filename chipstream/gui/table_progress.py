from PyQt6 import QtCore, QtWidgets


class ProgressTable(QtWidgets.QTableWidget):
    row_selected = QtCore.pyqtSignal(int)

    def __init__(self, *args, **kwargs):
        super(ProgressTable, self).__init__(*args, **kwargs)
        self.job_manager = None

        # signals
        self.itemSelectionChanged.connect(
            self.on_selection_changed)

        # timer for updating table contents
        self.monitor_timer = QtCore.QTimer(self)
        self.monitor_timer.timeout.connect(
            self.update_from_job_manager_progress)
        self.monitor_timer.start(300)

    @QtCore.pyqtSlot()
    def on_selection_changed(self):
        """Emit a row-selected signal"""
        row = self.currentIndex().row()
        self.row_selected.emit(row)

    def set_job_manager(self, job_manager):
        if self.job_manager is None:
            self.job_manager = job_manager
        else:
            raise ValueError("Job manager already set!")

    def set_item_label(self, row, col, label, align=None):
        """Get/Create a Qlabel at the specified position
        """
        label = f"{label}"
        item = self.item(row, col)
        if item is None:
            item = QtWidgets.QTableWidgetItem(label)
            self.setItem(row, col, item)
            if align is not None:
                item.setTextAlignment(align)
        else:
            if item.text() != label:
                item.setText(label)

    def set_item_progress(self, row, col, progress):
        """Get/Create a QProgressBar at the specified position
        """
        pb = self.cellWidget(row, col)
        if pb is None:
            pb = QtWidgets.QProgressBar(self)
            pb.setMaximum(1000)
            self.setCellWidget(row, col, pb)
        else:
            if pb.value() != int(progress*1000):
                pb.setValue(int(progress*1000))

    @QtCore.pyqtSlot()
    def update_from_job_manager(self):
        if self.job_manager is None:
            raise ValueError("Job manager not set!")
        self.setRowCount(len(self.job_manager))
        # Check rows and populate new items
        for ii in range(len(self.job_manager)):
            status = self.job_manager[ii]
            self.set_item_label(ii, 0, str(status["path"]))
            self.set_item_label(ii, 1, str(status["state"]),
                                align=QtCore.Qt.AlignmentFlag.AlignCenter)
            self.set_item_progress(ii, 2, status["progress"])
        # Set path column width to something large (does not work during init)
        if self.columnWidth(0) == 100:
            self.setColumnWidth(0, 500)

    @QtCore.pyqtSlot()
    def update_from_job_manager_progress(self):
        if self.job_manager:
            for ii in range(len(self.job_manager)):
                st = self.item(ii, 1)
                st.setText(self.job_manager[ii]["state"])
                pb = self.cellWidget(ii, 2)
                progress = self.job_manager[ii]["progress"]
                if pb is not None and pb.value() != int(progress*1000):
                    pb.setValue(int(progress*1000))
