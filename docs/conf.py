import pathlib
import tomllib

import chipstream
# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'ChipStream'
github_project = 'DC-analysis/' + project

with (pathlib.Path(__file__).parent.parent / "pyproject.toml").open("rb") as f:
    data = tomllib.load(f)
authors = [a["name"] for a in data["project"]["authors"]]
author = ", ".join(authors)
copyright = '2023, ' + author
release = chipstream.__version__

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = []

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']


# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    "python": ('https://docs.python.org/', None),
    "dclab": ('https://dclab.readthedocs.io/en/stable/', None),
    "dcnum": ('https://dcnum.readthedocs.io/en/stable/', None),
    "h5py": ('https://h5py.readthedocs.io/en/stable/', None),
    "numpy": ('https://docs.scipy.org/doc/numpy/', None),
    }
