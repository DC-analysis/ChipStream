import shutil
import subprocess
import sys

import dcnum.read
import h5py
import numpy as np

import pytest

from helper_methods import retrieve_data, retrieve_model

pytest.importorskip("click")

import dcnum  # noqa: E402
import chipstream  # noqa: E402
from chipstream.cli import cli_main, cli_valid  # noqa: E402


@pytest.mark.parametrize("drain", [True, False])
def test_cli_basins(cli_runner, drain):
    path_temp = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    path = path_temp.with_name("input_path.rtdc")

    # create a test file for more than 100 events
    with dcnum.read.concatenated_hdf5_data(
        paths=3*[path_temp],
        path_out=path,
            compute_frame=True):
        pass

    path_out = path.with_name("with_pixel_size_dcn.rtdc")
    args = [str(path),
            str(path_out),
            "-s", "thresh",
            ]
    if drain:
        args.append("--drain-basins")
    result = cli_runner.invoke(cli_main.chipstream_cli, args)
    assert result.exit_code == 0

    with h5py.File(path_out) as h5:
        for feat in ["image", "frame"]:
            if drain:
                assert feat in h5["events"]
            else:
                assert feat not in h5["events"]
        for feat in ["mask", "deform", "aspect"]:
            assert feat in h5["events"]


def test_cli_compression(cli_runner):
    path_temp = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    path = path_temp.with_name("input_path.rtdc")

    # create a test file for more than 100 events
    with dcnum.read.concatenated_hdf5_data(
        paths=3*[path_temp],
        path_out=path,
            compute_frame=True):
        pass

    path_out = path.with_name("output.rtdc")
    args = [str(path),
            str(path_out),
            "-s", "thresh",
            "-c", "zstd-2",
            ]

    result = cli_runner.invoke(cli_main.chipstream_cli, args)
    assert result.exit_code == 0

    with h5py.File(path_out) as h5:
        for feat in ["mask", "deform", "aspect"]:
            assert feat in h5["events"]
            create_plist = h5["events"][feat].id.get_create_plist()
            filter_args = create_plist.get_filter_by_id(32015)
            assert filter_args[1] == (2,)


@pytest.mark.parametrize("add_flickering", [True, False])
def test_cli_flickering_correction(cli_runner, add_flickering):
    path_temp = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    path = path_temp.with_name("input_path.rtdc")

    # create a test file for more than 100 events
    with dcnum.read.concatenated_hdf5_data(
        paths=3*[path_temp],
        path_out=path,
            compute_frame=True):
        pass

    if add_flickering:
        # provoke offset correction in CLI
        with h5py.File(path, "a") as h5:
            size = len(h5["events/image"])
            images_orig = h5["events/image"]
            del h5["events/image"]
            offset = np.zeros((size, 1, 1), dtype=np.uint8)
            # add flickering every five frames
            offset[::5] += 5
            h5["events/image"] = np.array(
                images_orig + offset,
                dtype=np.uint8
            )

    path_out = path.with_name("flickering_test.rtdc")
    args = [str(path),
            str(path_out),
            "-s", "thresh",
            ]

    result = cli_runner.invoke(cli_main.chipstream_cli, args)
    assert result.exit_code == 0

    with h5py.File(path_out) as h5:
        if add_flickering:
            assert h5.attrs["pipeline:dcnum background"] \
                   == "sparsemed:k=200^s=1^t=0^f=0.8^o=1"
            assert "bg_off" in h5["events"]
        else:
            assert h5.attrs["pipeline:dcnum background"] \
                   == "sparsemed:k=200^s=1^t=0^f=0.8^o=0"
            assert "bg_off" not in h5["events"]


def test_invalid_input_data_no_image_data(cli_runner):
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    with h5py.File(path, "a") as h5:
        del h5["events/image"]

    path_out = path.with_name("limited_events.rtdc")

    result = cli_runner.invoke(cli_main.chipstream_cli,
                               [str(path),
                                str(path_out),
                                ])
    assert result.exit_code == 1
    assert result.stderr.count("No image data found in input")


def test_invalid_input_data_bad_format(cli_runner, tmp_path):
    path = tmp_path / "test.rtdc"
    path.write_text("hello world")

    path_out = path.with_name("limited_events.rtdc")

    result = cli_runner.invoke(cli_main.chipstream_cli,
                               [str(path),
                                str(path_out),
                                ])
    assert result.exit_code == 1
    assert result.stderr.count("Not a valid input file")


@pytest.mark.parametrize("args,message", [
    # missing "="
    [["-ks", "thresh"], "Expected 'KEY=VALUE', got 'thresh'"],
    # missing key
    [["-kb", "=5"], "Expected 'KEY=VALUE', got '=5'"],
    # only the first "=" separates key and value
    [["-ks", "thresh=1=2"], "Invalid value '1=2' for keyword 'thresh'"],
    # unknown keywords
    [["-ks", "peter=3"], "Invalid keyword 'peter' for 'thresh'"],
    [["-kb", "peter=3"], "Invalid keyword 'peter' for 'sparsemed'"],
    [["-kf", "peter=3"], "Invalid keyword 'peter' for 'legacy'"],
    [["-kg", "peter=3"], "Invalid keyword 'peter' for gating"],
    # invalid values
    [["-kb", "kernel_size=abc"], "Invalid value 'abc' for keyword"],
    [["-kf", "haralick=maybe"], "Invalid value 'maybe' for keyword"],
    [["-kg", "size_thresh_mask=abc"], "Invalid value 'abc' for keyword"],
    # None is only allowed if the keyword argument accepts None
    [["-ks", "thresh=None"], "Invalid value 'None' for keyword"],
])
def test_cli_kwargs_invalid(cli_runner, args, message):
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    result = cli_runner.invoke(cli_main.chipstream_cli,
                               [str(path), "--dry-run"] + args)
    assert result.exit_code == 2
    assert result.stderr.count(f"Invalid value for '{args[0]}'")
    assert result.stderr.count(message)


@pytest.mark.parametrize("value", ["None", "none", "10"])
def test_cli_kwargs_none(cli_runner, value):
    """The default "None" shown in the help string must be accepted"""
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    result = cli_runner.invoke(cli_main.chipstream_cli,
                               [str(path), "--dry-run",
                                "-kg", f"size_thresh_mask={value}"])
    assert result.exit_code == 0
    assert result.stdout.count("Gate ID:\tnorm:o=0^s=10")


def test_cli_kwargs_split_first_equal_sign():
    assert cli_valid.split_kwargs(["model_file=/path/a=b/m.dcnm",
                                   "thresh=-3"], "-ks") == [
        ("model_file", "/path/a=b/m.dcnm"),
        ("thresh", "-3"),
    ]


def test_cli_kwargs_value_with_equal_sign():
    pytest.importorskip("torch")
    kwargs = cli_valid.validate_segmentation_kwargs(
        "torchmpo", ["model_file=/path/a=b/m.dcnm", "closing_disk=3"])
    assert kwargs["model_file"] == "/path/a=b/m.dcnm"
    assert kwargs["kwargs_mask"] == {"closing_disk": 3}


@pytest.mark.parametrize("limit_events,dcnum_mapping,dcnum_yield,f0", [
    # this is the default
    ["0", "0", 36, 1],
    ["1-4", "1-4-n", 6, 2],
    ["3-10-5", "3-10-5", 5, 4],
    # all events
    ["00", "0", 36, 1],
    ["n", "0", 36, 1],
    # open ranges
    ["n-4", "n-4-n", 7, 1],
    ["10-n", "10-n-n", 27, 6],
    # beyond the dataset size (limited to the dataset size by dcnum)
    ["1000", "1000", 36, 1],
    ["10-1000-2", "10-1000-2", 26, 6],
])
def test_cli_limit_events(cli_runner, limit_events, dcnum_yield,
                          dcnum_mapping, f0):
    path_temp = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    path = path_temp.with_name("input_path.rtdc")

    # create a test file for more than 100 events
    with dcnum.read.concatenated_hdf5_data(
        paths=3*[path_temp],
        path_out=path,
            compute_frame=True):
        pass

    # sanity check
    with h5py.File(path) as h5:
        assert np.all(h5["events/frame"][:]
                      == np.array([1,  2,  2,  4,  4,  5,  5,  5,  6,  6,
                                   6,  7,  8,  8, 10, 10, 11, 11, 11, 12,
                                   12, 12, 13, 14, 14, 16, 16, 17, 17, 17,
                                   18, 18, 18]))
        assert "basinmap0" not in h5

    path_out = path.with_name("limited_events.rtdc")
    result = cli_runner.invoke(cli_main.chipstream_cli,
                               [str(path),
                                str(path_out),
                                "-kb", "offset_correction=true",
                                "-s", "thresh",
                                "--limit-events", limit_events,
                                "--drain-basins",
                                ])
    assert result.exit_code == 0

    with h5py.File(path_out) as h5:
        assert h5["events/frame"][0] == f0
        assert h5.attrs["pipeline:dcnum background"] == \
               "sparsemed:k=200^s=1^t=0^f=0.8^o=1"
        assert h5.attrs["pipeline:dcnum yield"] == dcnum_yield
        assert h5.attrs["pipeline:dcnum mapping"] == dcnum_mapping
        assert h5.attrs["experiment:event count"] == dcnum_yield


def test_cli_python_m():
    """Run the CLI via `python -m chipstream.cli`"""
    result = subprocess.run(
        [sys.executable, "-m", "chipstream.cli", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert chipstream.__version__ in result.stdout


@pytest.mark.parametrize("use_path_out", [True, False])
def test_cli_recursive_continue_after_failure(cli_runner, tmp_path,
                                              use_path_out):
    """A file that fails must not stop the other files from processing"""
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    dir_in = tmp_path / "in"
    dir_in.mkdir()
    # sorted before the valid file
    (dir_in / "a_bad.rtdc").write_text("hello world")
    shutil.copy2(path, dir_in / "b_good.rtdc")
    dir_out = tmp_path / "out" if use_path_out else dir_in

    args = [str(dir_in), "--recursive", "--debug"]
    if use_path_out:
        args.append(str(dir_out))
    result = cli_runner.invoke(cli_main.chipstream_cli, args)
    assert result.exit_code == 1
    assert result.stdout.count("Failed to process")
    assert result.stdout.count("Not a valid input file")
    assert result.stdout.count("Could not process 1 file(s)")
    assert not (dir_out / "a_bad_dcn.rtdc").exists()
    assert (dir_out / "b_good_dcn.rtdc").exists()


@pytest.mark.parametrize("use_path_out", [True, False])
def test_cli_recursive_skip_existing_output(cli_runner, tmp_path,
                                            use_path_out):
    """Files with an existing output file are skipped (resume a batch)"""
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    dir_in = tmp_path / "in"
    dir_in.mkdir()
    shutil.copy2(path, dir_in / "a.rtdc")
    shutil.copy2(path, dir_in / "b.rtdc")
    dir_out = tmp_path / "out" if use_path_out else dir_in
    dir_out.mkdir(exist_ok=True)
    # output of a previous (interrupted) run
    (dir_out / "a_dcn.rtdc").write_text("previous output")

    args = [str(dir_in), "--recursive", "--debug"]
    if use_path_out:
        args.append(str(dir_out))
    result = cli_runner.invoke(cli_main.chipstream_cli, args)
    assert result.exit_code == 0
    assert result.stdout.count("Skipping")
    assert result.stdout.count("Skipped 1 file(s) with existing output")
    # existing output is not touched
    assert (dir_out / "a_dcn.rtdc").read_text() == "previous output"
    with h5py.File(dir_out / "b_dcn.rtdc") as h5:
        assert "deform" in h5["events"]


def test_cli_recursive_invalid_kwargs(cli_runner, tmp_path):
    """Invalid command-line arguments abort the batch"""
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    dir_in = tmp_path / "in"
    dir_in.mkdir()
    shutil.copy2(path, dir_in / "a.rtdc")
    shutil.copy2(path, dir_in / "b.rtdc")
    result = cli_runner.invoke(cli_main.chipstream_cli,
                               [str(dir_in), "--recursive", "--debug",
                                "-ks", "peter=3"])
    assert result.exit_code == 2
    assert result.stderr.count("Invalid keyword 'peter' for 'thresh'")
    # the batch is aborted at the first file
    assert not result.stdout.count("b.rtdc")
    assert not (dir_in / "a_dcn.rtdc").exists()
    assert not (dir_in / "b_dcn.rtdc").exists()


def test_cli_recursive_with_file(cli_runner):
    """Recursive mode requires a directory as input"""
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    result = cli_runner.invoke(cli_main.chipstream_cli,
                               [str(path), "--recursive"])
    assert result.exit_code == 1
    assert result.stdout.count("must be a directory in recursive mode")
    assert not path.with_name(path.stem + "_dcn.rtdc").exists()


@pytest.mark.parametrize("limit_events,message", [
    ["-5", "Missing start in '-5'"],
    ["5--2", "Missing stop in '5--2'"],
    ["5-", "Missing stop in '5-'"],
    ["a", "Invalid number of events 'a'"],
    ["5-b", "Invalid stop 'b'"],
    ["5-7-0", "the step must not be zero"],
    ["5-2", "the start must be smaller than the stop"],
    ["5-5", "the start must be smaller than the stop"],
    ["1-2-3-4", "expected 'START-STOP' or 'START-STOP-STEP'"],
])
def test_cli_limit_events_invalid(cli_runner, limit_events, message):
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    result = cli_runner.invoke(cli_main.chipstream_cli,
                               [str(path),
                                "--dry-run",
                                "--limit-events", limit_events,
                                ])
    assert result.exit_code == 2
    assert result.stderr.count("Invalid value for '--limit-events'")
    assert result.stderr.count(message)


@pytest.mark.parametrize("limit_events,index_mapping", [
    ["0", None],
    ["00", None],
    ["n", None],
    ["5", 5],
    ["5-n", slice(5, None, None)],
    ["n-5", slice(None, 5, None)],
    ["n-n-2", slice(None, None, 2)],
    ["5-10", slice(5, 10, None)],
    ["5-10-2", slice(5, 10, 2)],
])
def test_cli_limit_events_parse(limit_events, index_mapping):
    assert cli_main.parse_limit_events(
        None, None, limit_events) == index_mapping


def test_cli_set_pixel_size(cli_runner):
    path_temp = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    path = path_temp.with_name("input_path.rtdc")

    # create a test file for more than 100 events
    with dcnum.read.concatenated_hdf5_data(
        paths=3*[path_temp],
        path_out=path,
            compute_frame=True):
        pass

    # remove the pixel size from the input data
    with h5py.File(path, "a") as h5:
        del h5.attrs["imaging:pixel size"]

    path_out = path.with_name("with_pixel_size_dcn.rtdc")
    result = cli_runner.invoke(cli_main.chipstream_cli,
                               [str(path),
                                str(path_out),
                                "-s", "thresh",
                                "-p", "0.266",
                                ])
    assert result.exit_code == 0

    with h5py.File(path_out) as h5:
        assert h5.attrs["imaging:pixel size"] == 0.266


@pytest.mark.parametrize("method,kwarg,ppid", [
    ["sparsemed", "offset_correction=0", "sparsemed:k=200^s=1^t=0^f=0.8^o=0"],
    ["rollmed", "kernel_size=12", "rollmed:k=12^b=10000"],
])
def test_cli_set_background(cli_runner, method, kwarg, ppid):
    path_temp = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    path = path_temp.with_name("input_path.rtdc")

    # create a test file for more than 100 events
    with dcnum.read.concatenated_hdf5_data(
        paths=3*[path_temp],
        path_out=path,
            compute_frame=True):
        pass

    path_out = path.with_name("output.rtdc")
    result = cli_runner.invoke(cli_main.chipstream_cli,
                               [str(path),
                                str(path_out),
                                "-b", method,
                                "-kb", kwarg,
                                ])
    assert result.exit_code == 0

    with h5py.File(path_out) as h5:
        assert h5.attrs["pipeline:dcnum background"] == ppid


def test_cli_torchmpo(cli_runner):
    pytest.importorskip("torch")
    mpath = retrieve_model("segm-torch-model_unet-dcnum-test_g1_910c2.zip")
    path_temp = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    path = path_temp.with_name("input_path.rtdc")

    # create a test file for more than 100 events
    with dcnum.read.concatenated_hdf5_data(
        paths=3*[path_temp],
        path_out=path,
            compute_frame=True):
        pass

    path_out = path.with_name("output.rtdc")
    result = cli_runner.invoke(cli_main.chipstream_cli,
                               [str(path),
                                str(path_out),
                                "-s", "torchmpo",
                                "-ks", f"model_file={mpath}",
                                ])
    assert result.exit_code == 0

    with h5py.File(path_out) as h5:
        assert h5.attrs["pipeline:dcnum segmenter"] \
               == "torchmpo:m=unet-dcnum-test_g1_910c2.dcnm:cle=1^f=1^clo=0"
        assert np.sum(np.array(h5["events/mask"][2], dtype=bool)) == 828
        assert np.allclose(h5["events/area_um"][10], 56.17808075)


def test_cli_torchmpo_wrong_model(cli_runner):
    pytest.importorskip("torch")
    mpath = retrieve_model("segm-torch-model_unet-dcnum-test_g1_910c2.zip")
    path_temp = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")
    path = path_temp.with_name("input_path.rtdc")

    # create a test file for more than 100 events
    with dcnum.read.concatenated_hdf5_data(
        paths=3*[path_temp],
        path_out=path,
            compute_frame=True):
        pass

    # change the region to reservoir, so the model will fail
    with h5py.File(path, "a") as h5:
        h5.attrs["setup:chip region"] = "reservoir"

    path_out = path.with_name("output.rtdc")
    result = cli_runner.invoke(cli_main.chipstream_cli,
                               [str(path),
                                str(path_out),
                                "-s", "torchmpo",
                                "-ks", f"model_file={mpath}",
                                ])
    assert result.exit_code == 1
    assert result.stderr.count("only experiments in channel region supported")


def test_z_cli_info(cli_runner):
    result = cli_runner.invoke(cli_main.chipstream_cli,
                               ["--info"])
    assert result.exit_code == 0
    data = {}
    for line in result.stdout.split("\n"):
        if line.count(":"):
            var, val = line.split(":", 1)
            data[var.strip()] = val.strip()
    assert "chipstream version" in data
    assert data["chipstream version"] == chipstream.__version__
    assert data["dcnum version"] == dcnum.__version__
    assert "dcnum version" in data
    assert "CUDA compute available" in data
    assert data["CUDA compute available"] in ["true", "false"]
