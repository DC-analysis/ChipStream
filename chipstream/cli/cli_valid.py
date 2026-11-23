import inspect
import types
import typing
from typing import Any, get_type_hints
import warnings

import click
from dcnum.meta import ppid
import dcnum.read
import h5py

from . import cli_common as cm


def convert_kwarg_value(key: str,
                        value: str,
                        dtype: Any,
                        option: str) -> Any:
    """Convert a command-line keyword argument value to `dtype`

    The string "None" (case-insensitive) is converted to `None` if
    `dtype` allows `None`.

    Raises
    ------
    click.BadParameter
        if the value cannot be converted
    """
    if (value.lower() == "none"
            and typing.get_origin(dtype) in {typing.Union, types.UnionType}
            and type(None) in typing.get_args(dtype)):
        return None
    try:
        return ppid.convert_to_dtype(value, dtype)
    except (TypeError, ValueError) as e:
        dtype_name = getattr(dtype, "__name__", str(dtype))
        raise click.BadParameter(
            f"Invalid value '{value}' for keyword '{key}' "
            f"(expected {dtype_name}): {e}",
            param_hint=f"'{option}'")


def split_kwargs(args: list[str], option: str) -> list[tuple[str, str]]:
    """Split command-line `KEY=VALUE` arguments into key-value pairs

    Only the first "=" separates the key from the value, so the
    value may contain "=" (e.g. in a file path).

    Raises
    ------
    click.BadParameter
        if an argument has no "=" or an empty key
    """
    pairs = []
    for arg in args or []:
        key, sep, value = arg.partition("=")
        key = key.strip()
        if not sep or not key:
            raise click.BadParameter(
                f"Expected 'KEY=VALUE', got '{arg}'",
                param_hint=f"'{option}'")
        pairs.append((key, value))
    return pairs


def validate_background_kwargs(bg_method, args):
    """Parse background keyword arguments"""
    # Get list of valid keyword arguments
    bg_cls = cm.get_available_background_methods()[bg_method]
    spec = inspect.getfullargspec(bg_cls.check_user_kwargs)
    valid_kw = spec.kwonlyargs
    annot = get_type_hints(bg_cls.check_user_kwargs)
    # Convert the input args to key-value pairs
    kwargs = {}
    for key, value in split_kwargs(args, "-kb"):
        if key not in valid_kw:
            raise click.BadParameter(
                f"Invalid keyword '{key}' for '{bg_method}'. "
                f"Allowed keywords are {valid_kw}!",
                param_hint="'-kb'")
        # Convert to correct dtype (default to string)
        kwargs[key] = convert_kwarg_value(key, value, annot.get(key, str),
                                          "-kb")
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
    for key, value in split_kwargs(args, "-kf"):
        if key in valid_kw:
            kwargs[key] = convert_kwarg_value(
                key, value, annot.get(key, str), "-kf")
        else:
            raise click.BadParameter(
                f"Invalid keyword '{key}' for '{feat_code}'. "
                f"Allowed keywords are {valid_kw}!",
                param_hint="'-kf'")
    return kwargs


def validate_gate_kwargs(args: list[str]) -> dict[str, Any]:
    spec = inspect.getfullargspec(cm.Gate.__init__)
    valid_kw = spec.kwonlyargs
    annot = get_type_hints(cm.Gate.__init__)
    # Convert the input args to key-value pairs
    kwargs = {}
    for key, value in split_kwargs(args, "-kg"):
        if key in valid_kw:
            kwargs[key] = convert_kwarg_value(
                key, value, annot.get(key, str), "-kg")
        else:
            raise click.BadParameter(
                f"Invalid keyword '{key}' for gating. "
                f"Allowed keywords are {valid_kw} (and box filters)!",
                param_hint="'-kg'")
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
    for key, value in split_kwargs(args, "-ks"):
        if key in valid_kw_mask:
            kwargs_mask[key] = convert_kwarg_value(
                key, value, annot_mask.get(key, str), "-ks")
        elif key in valid_kw:
            kwargs[key] = convert_kwarg_value(
                key, value, annot.get(key, str), "-ks")
        else:
            raise click.BadParameter(
                f"Invalid keyword '{key}' for '{seg_method}'. "
                f"Allowed keywords are {valid_kw + valid_kw_mask}!",
                param_hint="'-ks'")
    kwargs["kwargs_mask"] = kwargs_mask
    return kwargs
