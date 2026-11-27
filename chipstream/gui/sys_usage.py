import psutil
from PyQt6 import QtCore, QtWidgets


def get_nvidia_gpus():
    """Return the `pynvml` module and handles of all NVIDIA GPUs

    The GPU usage is read with NVIDIA's management library (NVML) via
    the package `nvidia-ml-py` (module `pynvml`). If that package, an
    NVIDIA driver, or an NVIDIA GPU is not available, `(None, [])` is
    returned.
    """
    try:
        import pynvml
        pynvml.nvmlInit()
        handles = [pynvml.nvmlDeviceGetHandleByIndex(ii)
                   for ii in range(pynvml.nvmlDeviceGetCount())]
    except Exception:
        # e.g. ImportError (no nvidia-ml-py) or pynvml.NVMLError
        # (no NVIDIA driver/library)
        return None, []
    return pynvml, handles


class SystemUsageLabel(QtWidgets.QLabel):
    """Status bar label showing the system-wide CPU, RAM, and GPU usage"""

    def __init__(self, *args, interval_ms: int = 2000, **kwargs):
        super().__init__(*args, **kwargs)
        self.setToolTip("System-wide CPU, memory, and NVIDIA GPU usage")
        self.nvml, self.gpu_handles = get_nvidia_gpus()
        # The first call to `cpu_percent` returns 0.0 and starts the
        # measurement period for the next call.
        psutil.cpu_percent(interval=None)
        self.update_usage()
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_usage)
        self.timer.start(interval_ms)

    def get_gpu_usage_text(self) -> str:
        """Return the GPU utilization and memory usage as text

        Returns an empty string if no NVIDIA GPU is available or if
        reading the GPU usage fails.
        """
        if self.nvml is None or not self.gpu_handles:
            return ""
        texts = []
        for ii, handle in enumerate(self.gpu_handles):
            try:
                util = self.nvml.nvmlDeviceGetUtilizationRates(handle).gpu
                mem = self.get_gpu_memory_info(handle)
            except Exception:
                # e.g. pynvml.NVMLError after the GPU was reset
                continue
            name = "GPU" if len(self.gpu_handles) == 1 else f"GPU{ii}"
            texts.append(f"{name} {util:.0f}% "
                         f"{mem.used / 1024**3:.1f} / "
                         f"{mem.total / 1024**3:.1f} GiB")
        return "   ".join(texts)

    def get_gpu_memory_info(self, handle):
        """Return the memory info of a GPU (`used` and `total` in bytes)

        If supported by the driver, the version 2 of the memory info is
        used, which (like `nvidia-smi`) does not count the memory that
        is reserved by the driver as used.
        """
        nvml = self.nvml
        assert nvml is not None, "only called if NVML is available"
        version = getattr(nvml, "nvmlMemory_v2", None)
        if version is not None:
            try:
                return nvml.nvmlDeviceGetMemoryInfo(handle, version=version)
            except Exception:
                # not supported by the driver
                pass
        return nvml.nvmlDeviceGetMemoryInfo(handle)

    @QtCore.pyqtSlot()
    def update_usage(self):
        """Update the label text with the current CPU, RAM, and GPU usage"""
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        used = (mem.total - mem.available) / 1024**3
        total = mem.total / 1024**3
        text = (f"CPU {cpu:.0f}%   "
                f"RAM {used:.1f} / {total:.1f} GiB ({mem.percent:.0f}%)")
        if gpu_text := self.get_gpu_usage_text():
            text += f"   {gpu_text}"
        self.setText(text)
