import psutil
from PyQt6 import QtCore, QtWidgets


class SystemUsageLabel(QtWidgets.QLabel):
    """Status bar label showing the system-wide CPU and RAM usage"""

    def __init__(self, *args, interval_ms: int = 2000, **kwargs):
        super().__init__(*args, **kwargs)
        self.setToolTip("System-wide CPU and memory usage")
        # The first call to `cpu_percent` returns 0.0 and starts the
        # measurement period for the next call.
        psutil.cpu_percent(interval=None)
        self.update_usage()
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_usage)
        self.timer.start(interval_ms)

    @QtCore.pyqtSlot()
    def update_usage(self):
        """Update the label text with the current CPU and RAM usage"""
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        used = (mem.total - mem.available) / 1024**3
        total = mem.total / 1024**3
        self.setText(f"CPU {cpu:.0f}%   "
                     f"RAM {used:.1f} / {total:.1f} GiB ({mem.percent:.0f}%)")
