import inspect
from typing import Any, get_type_hints
import warnings

from dcnum.meta import ppid
import dcnum.read
import h5py

from . import cli_common as cm


def validate_background_kwargs(bg_method, args):
    """Parse background keyword arguments"""
    # Get list of valid keyword arguments
    bg_cls = cm.get_available_background_methods()[bg_method]
    spec = inspect.getfullargspec(bg_cls.check_user_kwargs)
    valid_kw = spec.kwonlyargs
    annot = get_type_hints(bg_cls.check_user_kwargs)
    # Convert the input args to key-value pairs
    kwargs = {}
    for key, value in [a.split("=") for a in args]:
        if key not in valid_kw:
            raise ValueError(f"Invalid keyword '{key}' for {bg_method}. "
                             + f"Allowed keywords are {valid_kw}!")
        # Convert to correct dtype (default to string)
        kwargs[key] = ppid.convert_to_dtype(value, annot[key])
    return kwargs


def validate_feature_kwargs(args: list[str]) -> dict[str, Any]:
    # Get list of valid keyword arguments
    feat_cls = cm.QueueEventExtractor
    feat_code = feat_cls.get_ppid_code()
    # extract_approach
    spec = inspect.getfullargspec(feat_cls.get_events_from_masks)
    valid_kw = spec.kwonlyargs
    annot = get_type_hints(feat_cls.get_events_from_masks)
    # Convert the input args to key-value pairs
    kwargs = {}
    for key, value in [a.split("=") for a in args]:
        if key in valid_kw:
            kwargs[key] = ppid.convert_to_dtype(value, annot[key])
        else:
            raise ValueError(
                f"Invalid keyword '{key}' for '{feat_code}'. "
                f"Allowed keywords are {valid_kw}!")
    return kwargs


def validate_gate_kwargs(args: list[str]) -> dict[str, Any]:
    spec = inspect.getfullargspec(cm.Gate.__init__)
    valid_kw = spec.kwonlyargs
    annot = get_type_hints(cm.Gate.__init__)
    # Convert the input args to key-value pairs
    kwargs = {}
    for key, value in [a.split("=") for a in args]:
        if key in valid_kw:
            kwargs[key] = ppid.convert_to_dtype(value, annot[key])
        else:
            raise ValueError(
                f"Invalid keyword '{key}' for gating. "
                f"Allowed keywords are {valid_kw} (and box filters)!")
    return kwargs


def validate_pixel_size(data_path):
    with h5py.File(data_path) as h5:
        did = h5.attrs.get("setup:identifier", "EMPTY")
        pixel_size = h5.attrs.get("imaging:pixel size", 0)
        if (did.startswith("RC-")
                and (pixel_size < 0.255 or pixel_size > 0.275)):
            hd = dcnum.read.HDF5Data(h5, pixel_size=0.260)  # placeholder
            warnings.warn(
                f"Correcting for invalid pixel size in '{hd.path}'!")
            # Set default pixel size for Rivercyte devices
            # Check the logs for the device name used.
            logdat = hd.logs.get("cytoshot-acquisition", [])
            for line in logdat:
                line = line.strip().lower()
                if line.startswith("device name:"):
                    dev_name = line.split(":")[1].strip()
                    break
            else:
                # fall-back to old camera
                dev_name = "naiad 1.0"
            if dev_name == "naiad 1.0":
                # Naiad v1.0 camera VLXT06MI
                pixel_size = 0.2645
            elif dev_name == "naiad 1.1":
                # Naiad v1.1 camera VCXU213M
                pixel_size = 0.2675
            else:
                warnings.warn(f"Unknown device name: '{dev_name}'; "
                              f"Not changing pixel size {pixel_size}")
        return pixel_size


def validate_segmentation_kwargs(seg_method, args):
    """Parse segmenter keyword arguments"""
    # Get list of valid keyword arguments
    seg_cls = cm.get_segmenters()[seg_method]
    # segment_algorithm
    spec_appr = inspect.getfullargspec(seg_cls.segment_algorithm)
    valid_kw = spec_appr.kwonlyargs
    annot = get_type_hints(seg_cls.segment_algorithm)

    # process_mask
    if seg_cls.mask_postprocessing:
        spec_mask = inspect.getfullargspec(seg_cls.process_labels)
        valid_kw_mask = spec_mask.kwonlyargs
        annot_mask = get_type_hints(seg_cls.process_labels)
    else:
        valid_kw_mask = []
        annot_mask = {}

    # Convert the input args to key-value pairs
    kwargs = {}
    kwargs_mask = {}
    for key, value in [a.split("=") for a in args]:
        if key in valid_kw_mask:
            kwargs_mask[key] = ppid.convert_to_dtype(value, annot_mask[key])
        elif key in valid_kw:
            kwargs[key] = ppid.convert_to_dtype(value, annot[key])
        else:
            raise ValueError(
                f"Invalid keyword '{key}' for {seg_method}. "
                f"Allowed keywords are {valid_kw + valid_kw_mask}!")
    kwargs["kwargs_mask"] = kwargs_mask
    return kwargs
