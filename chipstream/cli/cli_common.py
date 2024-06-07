import logging

from dcnum.feat.feat_background import get_available_background_methods
from dcnum.feat import Gate, QueueEventExtractor  # noqa: F401
from dcnum.meta.ppid import get_class_method_info
from dcnum.segm import get_available_segmenters


seg_methods = get_available_segmenters()
bg_methods = get_available_background_methods()


class PrettyFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(levelname)s %(name)s: %(message)s"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def format_help_class_method_info(info_list):
    """Format a list of `info` dictionaries from `get_class_method_info`"""
    choices = ["\b"]  # "\b" means paragraph is not formatted in help string
    for info in info_list:
        code = info["code"]
        title = info["title"]
        choices.append(f" - '{code}': {title}")
        for mname in info.get("defaults", []):
            # We are flattening through all methods, because the CLI
            # makes them transparently available. There must not be
            # any name clashes, the developer is responsible for
            # that.
            kwds = info["defaults"][mname]
            if kwds:
                for kw in kwds:
                    choices.append(f"   - {kw}={kwds[kw]}")
    return "\n".join(choices)


def get_choices_help_string(class_dict, static_kw_methods=None):
    """Return a chipstream help string for this class

    Parameters
    ----------
    class_dict: dictionary of objects
        The dictionary holds the classes to inspect
    static_kw_methods: list of callable
        The methods to inspect; all kwargs-only keyword arguments
        are extracted.
    """
    info_list = []
    for key in class_dict:
        class_obj = class_dict[key]
        info_list.append(get_class_method_info(class_obj, static_kw_methods))
    return format_help_class_method_info(info_list)


def get_choices_help_string_segmenter(class_dict):
    """Return a chipstream help string for a segmenter class

    This is a custom function, analogous to get_choices_help_string,
    but for segmenters, which might or might not allow mask
    post-processing (depending on whether `mask_postprocessing` is set).

    Parameters
    ----------
    class_dict: dictionary of objects
        The dictionary holds the classes to inspect
    """
    info_list = []
    for key in class_dict:
        class_obj = class_dict[key]
        static_kw_methods = ["segment_algorithm"]
        static_kw_defaults = {}
        if class_obj.mask_postprocessing:
            static_kw_methods.append("process_mask")
            static_kw_defaults["process_mask"] = class_obj.mask_default_kwargs
        info_list.append(get_class_method_info(class_obj,
                                               static_kw_methods,
                                               static_kw_defaults))
    return format_help_class_method_info(info_list)
