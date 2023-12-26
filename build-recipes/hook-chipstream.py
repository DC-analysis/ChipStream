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
    "chipstream",
    "chipstream.cli",
    "chipstream.gui",
    "dcnum",
    "dcnum.feat",
    "dcnum.logic",
    "dcnum.meta",
    "dcnum.read",
    "dcnum.segm",
    "dcnum.write",
    "skimage.feature",
]

# Data files
datas = collect_data_files("chipstream", include_py_files=True)
datas += collect_data_files("chipstream", subdir="gui/img")

# Add the Zstandard library used by dclab
datas += collect_data_files("hdf5plugin", includes=["plugins/libh5zstd.*"])
