Installing ChipStream
=====================

You can download ChipStream installers from the `release page <https://github.com/DC-analysis/ChipStream/releases>`_.

Alternatively, you can install ChipStream via pip. If you have a CUDA-compatible
GPU and your Python installation cannot access the GPU (torch.cuda.is_available() is False),
please use the installation instructions from pytorch
(https://pytorch.org/get-started/locally/). For instance, if you have CUDA 12.1,
you can install torch with this pytorch.org index URL::

    # Install with CUDA/GPU support (does not work on macOS)
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

If you don't have a CUDA-capable GPU, you may install a light version of torch::

    # Only do this if you would like to have a light CPU-only version of torch
    pip install torch==2.3.1+cpu torchvision==0.18.1+cpu -f https://download.pytorch.org/whl/torch_stable.html

Finally, you can install ChipStream::

    pip install chipstream[all]


The ``[all]`` extra is an alias for ``[cli,gui,torch]``. With the capabilities:

 - ``cli``: command-line interface (``chipstream-cli`` command)
 - ``gui``: graphical user interface (``chipstream-gui`` command)
 - ``torch``: install PyTorch (machine-learning for segmentation)
