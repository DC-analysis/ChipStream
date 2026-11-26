"""GUI and CLI for deformability cytometry data postprocessing
Copyright (C) 2023 Paul Müller

This program is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
for more details.

You should have received a copy of the GNU General Public License along
with this program. If not, see <https://www.gnu.org/licenses/>.
"""
from dcnum.os_env_st import request_single_threaded

from ._version import __version__, __version_tuple__  # noqa: F401
from .torch_cache import setup_torch_inductor_cache_dir


request_single_threaded()
# Cache compiled PyTorch models persistently (set before dcnum spawns
# its worker processes, which inherit the environment).
setup_torch_inductor_cache_dir()
