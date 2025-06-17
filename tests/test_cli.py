import dcnum.read
import h5py
import numpy as np

import pytest

from helper_methods import retrieve_data, retrieve_model


pytest.importorskip("click")

from chipstream.cli import cli_main  # noqa: E402


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


@pytest.mark.parametrize("limit_events,dcnum_mapping,dcnum_yield,f0", [
    # this is the default
    ["0", "0", 36, 1],
    ["1-4", "1-4-n", 6, 2],
    ["3-10-5", "3-10-5", 5, 4],
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
