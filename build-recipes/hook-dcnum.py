# -----------------------------------------------------------------------------
# Copyright (c) 2019, PyInstaller Development Team.
#
# Distributed under the terms of the GNU General Public License with exception
# for distributing bootloader.
#
# The full license is in the file COPYING.txt, distributed with this software.
# -----------------------------------------------------------------------------

# Hook for MPL-Data-Cast
from PyInstaller.utils.hooks import collect_data_files

hiddenimports = [
    "cv2",
    "dcnum.feat",
    "dcnum.logic",
    "dcnum.meta",
    "dcnum.read",
    "dcnum.segm",
    "dcnum.write",
    "h5py",
    "mahotas",
    "numba",
    "numpy",
    "scipy.ndimage",
    "torch",
]

# Data files
datas = collect_data_files("dcnum", include_py_files=True)

# Add the Zstandard library used by dcnum
datas += collect_data_files("hdf5plugin", includes=["plugins/libh5zstd.*"])
