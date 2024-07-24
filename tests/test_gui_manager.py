import shutil

import pytest

from dcnum.meta import ppid

from chipstream.gui import manager

import h5py

from helper_methods import retrieve_data, retrieve_model


def test_manager_get_paths_out(tmp_path):
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")

    p1 = tmp_path / "foo" / "bar" / "data.rtdc"
    p2 = tmp_path / "foo" / "baz" / "data.rtdc"
    pout = tmp_path / "far"
    p1.parent.mkdir(exist_ok=True, parents=True)
    p2.parent.mkdir(exist_ok=True, parents=True)
    pout.mkdir(exist_ok=True, parents=True)
    shutil.copy2(path, p1)
    shutil.copy2(path, p2)

    mg = manager.ChipStreamJobManager()
    mg.add_path(p1)
    mg.add_path(p2)

    # Sanity check
    assert mg.get_paths_in()[0] == p1
    assert mg.get_paths_in()[1] == p2

    # If no output path is specified (None), then the returned
    # path list should just be the pats with "_dcn" inserted in the stem.
    assert mg.get_paths_out()[0] == p1.with_name(p1.stem + "_dcn.rtdc")
    assert mg.get_paths_out()[1] == p2.with_name(p2.stem + "_dcn.rtdc")

    # We now set the output path. The manager should now compute the
    # common parent path for all input paths and append relative
    # subdirectories.
    mg.set_output_path(pout)
    # Note that the common parent "foo" is missing.
    assert mg.get_paths_out()[0] == pout / "bar" / "data_dcn.rtdc"
    assert mg.get_paths_out()[1] == pout / "baz" / "data_dcn.rtdc"


def test_manager_read_data():
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")

    mg = manager.ChipStreamJobManager()
    assert len(mg) == 0
    mg.add_path(path)
    assert len(mg) == 1

    assert mg[0]["progress"] == 0
    assert mg[0]["state"] == "created"
    assert mg[0]["path"] == str(path)
    assert mg.current_index is None
    assert not mg.is_busy()
    assert mg.get_runner(0) is None
    assert mg.get_info(0) == "No job information available."

    # clear everything
    mg.clear()
    assert len(mg) == 0


def test_manager_run_defaults():
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")

    mg = manager.ChipStreamJobManager()
    mg.add_path(path)
    mg.run_all_in_thread()
    assert mg.is_busy()
    # wait for the thread to join
    mg.join()

    assert mg[0]["state"] == "done"
    assert mg[0]["progress"] == 1
    assert mg[0]["path"] == str(path)
    assert mg.current_index == 0
    assert not mg.is_busy()
    # default pipeline may change in dcnum
    assert mg.get_runner(0).ppid == (f"{ppid.DCNUM_PPID_GENERATION}|"
                                     "hdf:p=0.2645^i=0|"
                                     "sparsemed:k=200^s=1^t=0^f=0.8^o=0|"
                                     "thresh:t=-6:cle=1^f=1^clo=2|"
                                     "legacy:b=1^h=1^v=1|"
                                     "norm:o=0^s=10")


def test_manager_run_error_wrong_model():
    pytest.importorskip("torch")
    model_file = retrieve_model(
        "segm-torch-model_unet-dcnum-test_g1_910c2.zip")

    # Create a test dataset with metadata that will make the model invalid
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")

    with h5py.File(path, "a") as h5:
        h5.attrs["setup:chip region"] = "reservoir"

    mg = manager.ChipStreamJobManager()
    mg.add_path(path)
    mg.run_all_in_thread(job_kwargs={
        "segmenter_code": "torchmpo",
        "segmenter_kwargs": {"model_file": model_file}
        }
    )
    # wait for the thread to join
    mg.join()

    assert mg.current_index == 0
    assert mg[0]["progress"] == 0
    assert mg[0]["state"] == "error"
    assert mg.get_info(0).count("only experiments in channel region supported")

    assert not mg.is_busy()


def test_manager_run_with_path_out(tmp_path):
    path = retrieve_data(
        "fmt-hdf5_cytoshot_full-features_legacy_allev_2023.zip")

    p1 = tmp_path / "foo" / "bar" / "data.rtdc"
    p2 = tmp_path / "foo" / "baz" / "data.rtdc"
    pout = tmp_path / "far"
    p1.parent.mkdir(exist_ok=True, parents=True)
    p2.parent.mkdir(exist_ok=True, parents=True)
    pout.mkdir(exist_ok=True, parents=True)
    shutil.copy2(path, p1)
    shutil.copy2(path, p2)

    # set up manager
    mg = manager.ChipStreamJobManager()
    mg.add_path(p1)
    mg.add_path(p2)
    mg.set_output_path(pout)

    # start analysis
    mg.run_all_in_thread()
    # wait for the thread to join
    mg.join()

    # sanity checks
    assert mg[0]["progress"] == 1
    assert mg[0]["state"] == "done"
    assert mg[0]["path"] == str(p1)
    assert mg[1]["progress"] == 1
    assert mg[1]["state"] == "done"
    assert mg[1]["path"] == str(p2)
    assert mg.current_index == 1
    assert not mg.is_busy()

    # make sure the output paths exist
    assert (pout / "bar" / "data_dcn.rtdc").exists()
    assert (pout / "baz" / "data_dcn.rtdc").exists()
