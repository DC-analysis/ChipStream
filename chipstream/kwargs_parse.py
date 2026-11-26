"""Parse `KEY=VALUE` keyword arguments for the pipeline steps

Used by the command-line interface (`-kb`, `-ks`, `-kf`, `-kg`) and by
the expert settings of the GUI. This module does not depend on click.
"""
import inspect
import types
import typing
from typing import Any, get_type_hints

from dcnum.feat import Gate, QueueEventExtractor
from dcnum.feat.feat_background import get_available_background_methods
from dcnum.meta import ppid
from dcnum.segm import get_segmenters


class KeywordArgumentError(ValueError):
    """Invalid `KEY=VALUE` keyword argument"""

    def __init__(self, message: str, option: str):
        super().__init__(message)
        #: name of the option the argument belongs to (e.g. "-ks")
        self.option = option


def convert_kwarg_value(key: str,
                        value: str,
                        dtype: Any,
                        option: str) -> Any:
    """Convert a keyword argument value given as a string to `dtype`

    The string "None" (case-insensitive) is converted to `None` if
    `dtype` allows `None`.

    Raises
    ------
    KeywordArgumentError
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
        raise KeywordArgumentError(
            f"Invalid value '{value}' for keyword '{key}' "
            f"(expected {dtype_name}): {e}",
            option=option)


def split_kwargs(args: list[str] | None,
                 option: str) -> list[tuple[str, str]]:
    """Split `KEY=VALUE` arguments into key-value pairs

    Only the first "=" separates the key from the value, so the
    value may contain "=" (e.g. in a file path).

    Raises
    ------
    KeywordArgumentError
        if an argument has no "=" or an empty key
    """
    pairs = []
    for arg in args or []:
        key, sep, value = arg.partition("=")
        key = key.strip()
        if not sep or not key:
            raise KeywordArgumentError(f"Expected 'KEY=VALUE', got '{arg}'",
                                       option=option)
        pairs.append((key, value))
    return pairs


def parse_background_kwargs(bg_method: str,
                            args: list[str] | None,
                            option: str = "-kb") -> dict[str, Any]:
    """Parse background keyword arguments"""
    bg_cls = get_available_background_methods()[bg_method]
    spec = inspect.getfullargspec(bg_cls.check_user_kwargs)
    valid_kw = spec.kwonlyargs
    annot = get_type_hints(bg_cls.check_user_kwargs)
    kwargs = {}
    for key, value in split_kwargs(args, option):
        if key not in valid_kw:
            raise KeywordArgumentError(
                f"Invalid keyword '{key}' for '{bg_method}'. "
                f"Allowed keywords are {valid_kw}!",
                option=option)
        # Convert to correct dtype (default to string)
        kwargs[key] = convert_kwarg_value(key, value, annot.get(key, str),
                                          option)
    return kwargs


def parse_feature_kwargs(args: list[str] | None,
                         option: str = "-kf") -> dict[str, Any]:
    """Parse feature extraction keyword arguments"""
    feat_cls = QueueEventExtractor
    feat_code = feat_cls.get_ppid_code()
    spec = inspect.getfullargspec(feat_cls.get_events_from_masks)
    valid_kw = spec.kwonlyargs
    annot = get_type_hints(feat_cls.get_events_from_masks)
    kwargs = {}
    for key, value in split_kwargs(args, option):
        if key in valid_kw:
            kwargs[key] = convert_kwarg_value(
                key, value, annot.get(key, str), option)
        else:
            raise KeywordArgumentError(
                f"Invalid keyword '{key}' for '{feat_code}'. "
                f"Allowed keywords are {valid_kw}!",
                option=option)
    return kwargs


def parse_gate_kwargs(args: list[str] | None,
                      option: str = "-kg") -> dict[str, Any]:
    """Parse gating keyword arguments"""
    spec = inspect.getfullargspec(Gate.__init__)
    valid_kw = spec.kwonlyargs
    annot = get_type_hints(Gate.__init__)
    kwargs = {}
    for key, value in split_kwargs(args, option):
        if key in valid_kw:
            kwargs[key] = convert_kwarg_value(
                key, value, annot.get(key, str), option)
        else:
            raise KeywordArgumentError(
                f"Invalid keyword '{key}' for gating. "
                f"Allowed keywords are {valid_kw} (and box filters)!",
                option=option)
    return kwargs


def parse_segmentation_kwargs(seg_method: str,
                              args: list[str] | None,
                              option: str = "-ks") -> dict[str, Any]:
    """Parse segmenter keyword arguments

    The keyword arguments for mask post-processing are returned in
    the dictionary under the key "kwargs_mask".
    """
    seg_cls = get_segmenters()[seg_method]
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

    kwargs = {}
    kwargs_mask = {}
    for key, value in split_kwargs(args, option):
        if key in valid_kw_mask:
            kwargs_mask[key] = convert_kwarg_value(
                key, value, annot_mask.get(key, str), option)
        elif key in valid_kw:
            kwargs[key] = convert_kwarg_value(
                key, value, annot.get(key, str), option)
        else:
            raise KeywordArgumentError(
                f"Invalid keyword '{key}' for '{seg_method}'. "
                f"Allowed keywords are {valid_kw + valid_kw_mask}!",
                option=option)
    kwargs["kwargs_mask"] = kwargs_mask
    return kwargs
