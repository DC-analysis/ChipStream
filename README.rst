|ChipStream|
============

|PyPI Version| |Build Status| |Coverage Status| |Docs Status|


**ChipStream** is a graphical user interface for postprocessing
deformability cytometry (DC) data. This includes background computation,
event segmentation, and feature extraction.


Documentation
-------------

The documentation, is available at
`chipstream.readthedocs.io <https://chipstream.readthedocs.io>`__.


Installation
------------
Installers for Windows and macOS are available at the `release page
<https://github.com/DC-analysis/ChipStream/releases>`__.

If you have Python installed, you can install ChipStream from PyPI

::

    # graphical user interface
    pip install chipstream[gui]
    # command-line interface
    pip install chipstream[cli]
    # both
    pip install chipstream[cli, gui]


Execution
---------
If you have installed ChipStream from PyPI, you can start it with

::

    # graphical user interface
    chipstream-gui
    # command-line interface
    chipstream-cli


Citing ChipStream
-----------------
Please cite ChipStream either in-line

::

  (...) using the postprocessing software ChipStream version X.X.X
  (available at https://github.com/DC-analysis/ChipStream).

or in a bibliography

::

  Paul Müller and others (2023), ChipStream version X.X.X: Postprocessing
  software for deformability cytometry [Software]. Available at
  https://github.com/DC-analysis/ChipStream.

and replace ``X.X.X`` with the version of ChipStream that you used.


Testing
-------

::

    pip install -e .
    pip install -r tests/requirements.txt
    pytest tests


.. |ChipStream| image:: https://raw.github.com/DC-analysis/ChipStream/master/docs/artwork/chipstream_splash.png
.. |PyPI Version| image:: https://img.shields.io/pypi/v/ChipStream.svg
   :target: https://pypi.python.org/pypi/ChipStream
.. |Build Status| image:: https://img.shields.io/github/actions/workflow/status/DC-analysis/ChipStream/check.yml?branch=master
   :target: https://github.com/DC-analysis/ChipStream/actions?query=workflow%3AChecks
.. |Coverage Status| image:: https://img.shields.io/codecov/c/github/DC-analysis/ChipStream/master.svg
   :target: https://codecov.io/gh/DC-analysis/ChipStream
.. |Docs Status| image:: https://img.shields.io/readthedocs/chipstream
   :target: https://readthedocs.org/projects/chipstream/builds/
