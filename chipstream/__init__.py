# flake8: noqa: F401
import os

from ._version import __version__, __version_tuple__

# Disable multithreading for all major tools that could somehow
# parallelize our code. We don't want that, because we have linear
# code and rely on multiprocessing for parallelization. This has
# to be done before importing numpy or any other library affected.
# If someone uses dcevent in a script, they either have to import
# dcevent first, or set the environment variables manually.
# We use `setdefault` to honor any other variables set by the
# user for whatever reason.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
