Installing ChipStream
=====================

You can download ChipStream installers from the `release page <https://github.com/DC-analysis/ChipStream/releases>`_.

Alternatively, you can install ChipStream via pip::

    pip install chipstream[all]

If you don't need all dependencies, you can also install only a selection,
e.g. `cli,torch` if you are not planning to use the graphical user interface::

    pip install chipstream[cli,torch]

GPU Support
-----------
If you have a CUDA-compatible GPU and your Python installation cannot access
the GPU (torch.cuda.is_available() is False), please use the installation
instructions from pytorch (https://pytorch.org/get-started/locally/).
For instance, if your graphics card supports CUDA 12.9, you can install
torch with this pytorch.org index URL::

    # Install with CUDA/GPU support (does not work on macOS)
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu129

If your graphics card supports a newer CUDA version, you can check the backends
supported by pytorch (https://download.pytorch.org) and replace `cu129` with
e.g. `cu130` for CUDA 13.

CPU Support
-----------
If you don't have a CUDA-capable GPU, you may install a light version of torch::

    # Only do this if you would like to have a light CPU-only version of torch
    pip install torch==2.9.1+cpu torchvision==0.24.1+cpu --index-url https://download.pytorch.org/whl/cpu

Finally, you can install ChipStream::

    pip install chipstream[all]


The ``[all]`` extra is an alias for ``[cli,gui,torch]``. With the capabilities:

 - ``cli``: command-line interface (``chipstream-cli`` command)
 - ``gui``: graphical user interface (``chipstream-gui`` command)
 - ``torch``: install PyTorch (machine-learning for segmentation)
