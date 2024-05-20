import dcnum.read
import h5py

import pytest

from helper_methods import retrieve_data


pytest.importorskip("click")

from chipstream.cli import cli_main  # noqa: E402


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
        assert h5["events/frame"][0] == 1
        assert h5["events/frame"][1] == 2

    path_out = path.with_name("limited_events.rtdc")
    result = cli_runner.invoke(cli_main.chipstream_cli,
                               [str(path),
                                str(path_out),
                                "-s", "thresh",
                                "--limit-events", limit_events,
                                ])
    assert result.exit_code == 0

    with h5py.File(path_out) as h5:
        assert h5["events/frame"][0] == f0
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
