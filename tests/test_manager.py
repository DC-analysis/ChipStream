from chipstream import manager


from helper_methods import retrieve_data


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

    assert mg[0]["progress"] == 1
    assert mg[0]["state"] == "done"
    assert mg[0]["path"] == str(path)
    assert mg.current_index == 0
    assert not mg.is_busy()
    # default pipeline may change in dcnum
    assert mg.get_runner(0).ppid == ("7|"
                                     "hdf:p=0.2645|"
                                     "sparsemed:k=200^s=1^t=0^f=0.8|"
                                     "thresh:t=-6:cle=1^f=1^clo=2|"
                                     "legacy:b=1^h=1|"
                                     "norm:o=0^s=10")
