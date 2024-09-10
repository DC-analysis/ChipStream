import logging
import multiprocessing as mp
import pathlib
import sys

import click

from .._version import version

from . import cli_common as cm
from .cli_proc import process_dataset


@click.command(name="chipstream-cli",
               help=f"""
Segmentation and feature extraction for deformability cytometry data.

Read the image data from an input file, perform segmentation, feature
extraction, and gating.
If ``PATH_OUT`` is not specified, then the data are written to a new file
with the suffix "_dcn.rtdc". In recursive mode (``-r``), a target
directory may be specified.

You can specify which segmenter and feature extractor should be used.
You can also specify additional keyword arguments for
segmentation (``-ks``), feature extraction (``-kf``), and gating (``-kg``).

Available segmenters with keyword arguments:

{cm.get_choices_help_string_segmenter(cm.seg_methods)}

Available feature extractors:

{cm.get_choices_help_string({"legacy": cm.QueueEventExtractor},
                            ["get_events_from_masks"])}

Available gating options:

{cm.get_choices_help_string({"": cm.Gate}, ["__init__"])}


Examples:

Process an .rtdc measurement, without computing the Haralick texture features::

 chipstream-cli -kf haralick=False M001_data.rtdc

Recursively analyze a directory containing .rtdc files::

 chipstream-cli --recursive directory_name

""")
@click.argument("path_in",
                type=click.Path(exists=True,
                                dir_okay=True,
                                resolve_path=True,
                                path_type=pathlib.Path))
@click.argument("path_out",
                required=False,
                type=click.Path(dir_okay=True,
                                writable=True,
                                resolve_path=True,
                                path_type=pathlib.Path),
                )
@click.option("-b", "--background-method",
              type=click.Choice(sorted(cm.bg_methods.keys()),
                                case_sensitive=False),
              default="sparsemed", show_default=True,
              help="Background computation method to use.")
@click.option("-kb", "background_kwargs",
              multiple=True,
              help="Optional ``KEY=VALUE`` argument for the specified "
                   "background method",
              metavar="KEY=VALUE",
              )
@click.option("-s", "--segmentation-method",
              type=click.Choice(sorted(cm.seg_methods.keys()),
                                case_sensitive=False),
              default="thresh", show_default=True,
              help="Segmentation method to use.")
@click.option("-ks", "segmentation_kwargs",
              multiple=True,
              help="Optional ``KEY=VALUE`` argument for the specified "
                   "segmenter.",
              metavar="KEY=VALUE",
              )
@click.option("-kf", "feature_kwargs",
              multiple=True,
              help="Optional ``KEY=VALUE`` argument for the specified "
                   "feature extractor.",
              metavar="KEY=VALUE",
              )
@click.option("-kg", "gate_kwargs",
              multiple=True,
              help="Optional ``KEY=VALUE`` argument for event gating.",
              metavar="KEY=VALUE",
              )
@click.option("-p", "--pixel-size", type=float, default=0,
              help="Set/override the pixel size for feature "
                   "extraction [µm].")
@click.option("--limit-events", type=str, default="0",
              help="Limit events of events to analyze. This can be either "
                   "a number (e.g. '5000') or a range (e.g. '5000-7000'). "
                   "You can also specify a step size (e.g. '5000-7000-2' for "
                   "every second event). The convention follows Python slices "
                   "with 'n' substituting for 'None'.")
@click.option("--drain-basins", is_flag=True,
              help="Write all basin features from input to output file. This "
                   "option trades computation time and small file size for "
                   "an output file that contains all available features.")
@click.option("-r", "--recursive", is_flag=True,
              help="Recurse into subdirectories.")
@click.option("--num-cpus",
              type=click.IntRange(min=1, max=mp.cpu_count(), clamp=True),
              help="Number of processes to create."
              )
@click.option("--dry-run", is_flag=True,
              help="Only print the pipeline identifiers and exit.")
@click.option("--verbose", is_flag=True,
              help="Yield a more verbose output.")
@click.option("--debug", is_flag=True,
              help="Run chipstream in debugging mode. This disables "
                   "multiprocessing and yields a more verbose output.")
@click.version_option(version)
def chipstream_cli(
    path_in,
    path_out=None,
    background_method="sparsemed",
    background_kwargs=None,
    segmentation_method="thresh",
    segmentation_kwargs=None,
    feature_kwargs=None,
    gate_kwargs=None,
    pixel_size=0,
    limit_events="0",
    drain_basins=False,
    recursive=False,
    num_cpus=None,
    dry_run=False,
    verbose=False,
    debug=False,
):

    if debug:
        click.secho("Running in debug mode (this will be slow)",
                    fg="yellow")
        verbose = True

    # Parse limit_frames to get the HDF5Data index_mapping
    if limit_events == "0":
        index_mapping = None
    elif limit_events.count("-"):
        vals = limit_events.split("-")
        assert len(vals) in [2, 3], "slice definition must have length 2 or 3"
        start = None if vals[0] == "n" else int(vals[0])
        stop = None if vals[1] == "n" else int(vals[1])
        if len(vals) == 3:
            step = None if vals[2] == "n" else int(vals[2])
        else:
            step = None
        index_mapping = slice(start, stop, step)
    else:
        index_mapping = int(limit_events)

    # Tell the root logger to pretty-print logs
    root_logger = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(cm.PrettyFormatter())
    root_logger.addHandler(handler)
    handler.setLevel(logging.DEBUG if verbose else logging.WARNING)

    mp.freeze_support()

    process_kwargs = dict(
        background_method=background_method,
        background_kwargs=background_kwargs,
        segmentation_method=segmentation_method,
        segmentation_kwargs=segmentation_kwargs,
        feature_kwargs=feature_kwargs,
        gate_kwargs=gate_kwargs,
        pixel_size=pixel_size,
        index_mapping=index_mapping,
        # Below this line are arguments that do not define the pipeline ID
        basin_strategy="drain" if drain_basins else "tap",
        num_cpus=num_cpus or mp.cpu_count(),
        dry_run=dry_run,
        debug=debug,
        )

    if recursive:
        failed = 0  # keeps track of files that failed to process
        for pi in sorted(path_in.rglob("*.rtdc")):
            if pi.name.endswith("_dcn.rtdc"):
                continue
            if path_out is not None:
                poi = path_out / pi.relative_to(path_in)
                po = poi.with_name(poi.stem + "_dcn.rtdc")
                po.parent.mkdir(parents=True, exist_ok=True)
            else:
                po = None
            click.secho(f"\nProcessing {pi}")
            failed += process_dataset(path_in=pi,
                                      path_out=po,
                                      **process_kwargs)
            if dry_run:
                click.secho("Stopping dry run after one iteration")
                break
        if failed:
            click.secho(f"Could not process {failed} files", fg="red")
        exit_code = bool(failed)
    else:
        if path_in.is_dir():
            click.secho(f"PATH_IN must be a file, but '{path_in}' "
                        f"is a directory. Did you forget to specify "
                        f"the `--recursive` flag?", fg="red")
            exit_code = 1
        elif path_out and path_out.is_dir():
            click.secho(f"PATH_OUT must be a path to a file, but "
                        f"'{path_out}' is a directory")
            exit_code = 1
        else:
            # everything ok
            exit_code = process_dataset(path_in=path_in,
                                        path_out=path_out,
                                        **process_kwargs)
    if exit_code:
        click.secho("Encountered problems during processing", fg="red")
    sys.exit(exit_code)
