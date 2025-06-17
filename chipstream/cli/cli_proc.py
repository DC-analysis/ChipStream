import pathlib
import time
from typing import List, Literal

import click
import dcnum.logic
from dcnum.meta import ppid
import dcnum.read
import dcnum.segm

from . import cli_common as cm
from .cli_valid import (
    validate_background_kwargs, validate_feature_kwargs, validate_gate_kwargs,
    validate_pixel_size, validate_segmentation_kwargs
)


def process_dataset(
    path_in: pathlib.Path,
    path_out: pathlib.Path,
    background_method: str,
    background_kwargs: List[str],
    segmentation_method: str,
    segmentation_kwargs: List[str],
    feature_kwargs: List[str],
    gate_kwargs: List[str],
    pixel_size: float,
    index_mapping: int | slice | None,
    # Below this line are arguments that do not affect the pipeline ID
    basin_strategy: Literal["drain", "tap"],
    num_cpus: int,
    dry_run: bool,
    debug: bool,
):
    try:
        # Make sure the pixel size makes sense
        if pixel_size == 0:
            pixel_size = validate_pixel_size(data_path=path_in)

        # data keyword arguments
        data_kwargs = {"pixel_size": pixel_size,
                       "index_mapping": index_mapping}

        with dcnum.read.HDF5Data(path_in, **data_kwargs) as hd:
            # Before doing anything else, check whether we have image data in
            # the input file.
            has_data = hd.image is not None
            # Obtain the data PPID
            dat_id = hd.get_ppid()
    except BaseException:
        raise click.ClickException(
            f"Not a valid input file '{path_in}'.")

    if not has_data:
        raise click.ClickException(
            f"No image data found in input file '{path_in}'.")

    if path_out is None:
        path_out = path_in.with_name(path_in.stem + "_dcn.rtdc")
    path_out.parent.mkdir(parents=True, exist_ok=True)

    click.echo(f"Data ID:\t{dat_id}")

    # background keyword arguments
    bg_kwargs = validate_background_kwargs(background_method,
                                           background_kwargs)
    if (background_method == "sparsemed"
            and "offset_correction" not in bg_kwargs):
        # We are using the 'sparsemed' background algorithm, and the user
        # did not specify whether she wants to perform flickering
        # correction. Thus, we automatically check whether we need that.
        with dcnum.read.HDF5Data(path_in) as hd:
            bg_kwargs["offset_correction"] = \
                dcnum.read.detect_flickering(hd.image)
    bg_cls = cm.bg_methods[background_method]
    bg_id = bg_cls.get_ppid_from_ppkw(bg_kwargs)
    click.echo(f"Background ID:\t{bg_id}")

    # segmenter keyword arguments
    seg_kwargs = validate_segmentation_kwargs(segmentation_method,
                                              segmentation_kwargs)
    seg_cls = cm.seg_methods[segmentation_method]
    seg_id = seg_cls.get_ppid_from_ppkw(seg_kwargs)
    click.echo(f"Segmenter ID:\t{seg_id}")

    # feature keyword arguments
    feat_kwargs = validate_feature_kwargs(feature_kwargs)
    feat_cls = cm.QueueEventExtractor
    feat_id = feat_cls.get_ppid_from_ppkw(feat_kwargs)
    click.echo(f"Feature ID:\t{feat_id}")

    # gate keyword arguments
    gate_cls = cm.Gate
    gate_kwargs = validate_gate_kwargs(gate_kwargs)
    gate_id = gate_cls.get_ppid_from_ppkw(gate_kwargs)
    click.echo(f"Gate ID:\t{gate_id}")

    # compute pipeline hash
    pph = ppid.compute_pipeline_hash(
        gen_id=ppid.DCNUM_PPID_GENERATION,
        dat_id=dat_id,
        bg_id=bg_id,
        seg_id=seg_id,
        feat_id=feat_id,
        gate_id=gate_id)
    click.secho(f"Pipeline hash:\t{pph}")

    if dry_run:
        click.echo("Dry run complete")
        return 0

    job = dcnum.logic.DCNumPipelineJob(
        path_in=path_in,
        path_out=path_out,
        data_code="hdf",
        data_kwargs=data_kwargs,
        background_code=bg_cls.get_ppid_code(),
        background_kwargs=bg_kwargs,
        segmenter_code=seg_cls.get_ppid_code(),
        segmenter_kwargs=seg_kwargs,
        feature_code=feat_cls.get_ppid_code(),
        feature_kwargs=feat_kwargs,
        gate_code=gate_cls.get_ppid_code(),
        gate_kwargs=gate_kwargs,
        basin_strategy=basin_strategy,
        num_procs=num_cpus,
        debug=debug,
    )

    try:
        job.validate()
    except dcnum.segm.SegmenterNotApplicableError as e:
        raise click.ClickException(
            f"Segmenter '{segmentation_method}' cannot be applied "
            f"to '{path_in}': {', '.join(e.reasons_list)}")

    runner = dcnum.logic.DCNumJobRunner(job)
    runner.start()
    strlen = 0
    prev_str = ""
    while True:
        status = runner.get_status()
        progress = status["progress"]
        state = status["state"]
        print_str = f"Processing {progress:.0%} ({state})"
        if print_str != prev_str:  # don't clutter stdout
            strlen = max(strlen, len(print_str))
            print(print_str.ljust(strlen), end="\r", flush=True)
            prev_str = print_str
        if status["state"] in ["done", "error"]:
            break
        time.sleep(.3)  # don't use 100% CPU
    print("")  # new line

    if status["state"] == "error":
        runner.join(delete_temporary_files=False)
        raise click.ClickException(runner.error_tb)
    else:
        runner.join(delete_temporary_files=True)
        return 0
