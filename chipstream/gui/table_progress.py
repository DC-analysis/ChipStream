from PyQt6 import QtCore, QtWidgets

from .manager import ChipStreamJobManager


ItemProgressRole = QtCore.Qt.ItemDataRole.UserRole + 1001


class ProgressDelegate(QtWidgets.QStyledItemDelegate):
    def paint(self, painter, option, index):
        progress = index.data(ItemProgressRole)
        opt = QtWidgets.QStyleOptionProgressBar()
        opt.rect = option.rect
        opt.minimum = 0
        opt.maximum = 100
        opt.progress = int(progress * 100)
        opt.text = f"{progress:.1%}"
        opt.textVisible = True
        QtWidgets.QApplication.style().drawControl(
            QtWidgets.QStyle.ControlElement.CE_ProgressBar, opt, painter)


class ProgressModel(QtCore.QAbstractTableModel):
    def __init__(self, *args, **kwargs):
        super(ProgressModel, self).__init__(*args, **kwargs)
        self.manager = ChipStreamJobManager()
        self.map_columns = ["path", "state", "progress"]
        self.headers = [m.capitalize() for m in self.map_columns]
        self.monitor_timer = QtCore.QTimer(self)
        self.monitor_timer.timeout.connect(self.monitor_current_job)
        self.monitor_timer.start(300)

    def add_input_path(self, path):
        self.manager.add_path(path)
        self.layoutChanged.emit()

    def data(self, index, role):
        status = self.manager[index.row()]
        key = self.map_columns[index.column()]
        if role in [ItemProgressRole, QtCore.Qt.ItemDataRole.DisplayRole]:
            return status[key]
        else:
            return QtCore.QVariant()

    def columnCount(self, parent):
        return len(self.headers)

    def headerData(self, section, orientation, role):
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return QtCore.QVariant()
        return self.headers[section]

    def rowCount(self, parent):
        return len(self.manager)

    @QtCore.pyqtSlot()
    def monitor_current_job(self):
        current_index = self.manager.current_index
        if current_index is not None:
            self.update_index(current_index)

    @QtCore.pyqtSlot(int)
    def update_index(self, index):
        # update the row
        index_1 = self.index(index, 0)
        index_2 = self.index(index, len(self.headers))
        self.dataChanged.emit(index_1,
                              index_2,
                              [QtCore.Qt.ItemDataRole.DisplayRole,
                               QtCore.Qt.ItemDataRole.DisplayRole,
                               ItemProgressRole])


class ProgressTable(QtWidgets.QTableView):
    row_selected = QtCore.pyqtSignal(int)

    def __init__(self, *args, **kwargs):
        super(ProgressTable, self).__init__(*args, **kwargs)
        pbar_delegate = ProgressDelegate(self)
        self.setItemDelegateForColumn(2, pbar_delegate)
        self.model = ProgressModel()
        self.setModel(self.model)
        self.setColumnWidth(0, 400)
        self.setColumnWidth(1, 80)

        # signals
        self.selectionModel().selectionChanged.connect(
            self.on_selection_changed)

    def add_input_path(self, path):
        self.model.add_input_path(path)

    @QtCore.pyqtSlot()
    def on_selection_changed(self):
        """Emit a row-selected signal"""
        row = self.selectionModel().currentIndex().row()
        self.row_selected.emit(row)

    def update(self):
        self.model.dataChanged.emit()
