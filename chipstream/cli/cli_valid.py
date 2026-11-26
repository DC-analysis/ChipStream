import functools
import warnings

import click
import dcnum.read
import h5py

from .. import kwargs_parse


def _click_errors(func):
    """Convert `KeywordArgumentError` to `click.BadParameter`"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except kwargs_parse.KeywordArgumentError as e:
            raise click.BadParameter(str(e), param_hint=f"'{e.option}'")
    return wrapper


convert_kwarg_value = _click_errors(kwargs_parse.convert_kwarg_value)
split_kwargs = _click_errors(kwargs_parse.split_kwargs)
validate_background_kwargs = _click_errors(
    kwargs_parse.parse_background_kwargs)
validate_feature_kwargs = _click_errors(kwargs_parse.parse_feature_kwargs)
validate_gate_kwargs = _click_errors(kwargs_parse.parse_gate_kwargs)
validate_segmentation_kwargs = _click_errors(
    kwargs_parse.parse_segmentation_kwargs)


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
