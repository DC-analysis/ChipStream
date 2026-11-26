from __future__ import annotations

from collections.abc import Callable
import copy
from functools import lru_cache
import pathlib
import threading
import time
import traceback
import warnings

import dcnum.read
from dcnum import logic as dclogic
import h5py
import psutil


class JobStillRunningError(BaseException):
    pass


class ChipStreamJobManager:
    def __init__(self):
        #: Input path list containing tuples of (path, state-string) for
        #: each input path. This is a list that is shared with the worker
        #: thread and kept updated by the worker during the run.
        self._path_in_list = []
        #: Output directory for data processing. If set to None, files
        #: are created alongside the input files.
        self._path_out = None
        self._runner_list = []
        self._worker = None
        self.busy_lock = threading.Lock()
        #: set while the jobs are paused
        self._paused = threading.Event()
        #: processes suspended while paused (PID -> psutil.Process)
        self._suspended = {}
        self._suspend_lock = threading.Lock()
        self._suspender = None

    def __getitem__(self, index):
        runner = self.get_runner(index)
        if runner is None:
            status = {"progress": 0,
                      "state": self._path_in_list[index][1],
                      }
        else:
            status = runner.get_status()
            if (self.is_paused()
                    and index == self.current_index
                    and status["state"] not in ["done", "error"]):
                status["state"] = "paused"
        status["path"] = str(self._path_in_list[index][0])
        return status

    def __len__(self):
        return len(self._path_in_list)

    @property
    def current_index(self):
        return None if not self._runner_list else len(self._runner_list) - 1

    def add_path(self, path):
        if not self.is_busy():
            # Only append paths if we are currently not busy
            self._path_in_list.append([pathlib.Path(path), "created"])

    def clear(self):
        """Clear all data"""
        self._path_in_list.clear()
        self._runner_list.clear()
        self._worker = None

    def close(self, force=True):
        # Resume suspended processes, so that they can be stopped.
        self.resume()
        if force:
            # Get the current process
            proc = psutil.Process()
            # Forcibly kill all children. This is not very clean, and it
            # might leave zombie processes behind. But these zombie
            # processes will not be doing anything with data anymore.
            for _ in range(100):
                killed = 0
                children = list(proc.children(recursive=True))
                for child in children:
                    try:
                        child.kill()
                        killed += 1
                    except (psutil.ZombieProcess, psutil.NoSuchProcess):
                        continue
                if not killed:
                    break

            self.clear()
        elif self.is_busy():
            raise ValueError(
                "Manager is busy, use `force=True` to close regardless")

    def is_busy(self):
        return self.busy_lock.locked()

    def is_paused(self):
        """Whether the jobs are paused (see :meth:`pause`)"""
        return self._paused.is_set()

    def pause(self):
        """Pause the jobs by suspending all child processes

        All child processes of the current process (the worker
        processes of dcnum) are suspended with :func:`psutil.Process.suspend`.
        Since dcnum may start new processes while paused (e.g. while
        starting the workers or for the next job), new child processes
        are suspended in a background thread until :meth:`resume` is
        called. Threads in the current process are not suspended; they
        wait for the suspended processes.
        """
        with self._suspend_lock:
            if self._paused.is_set():
                return
            self._paused.set()
        self._suspend_children()
        self._suspender = threading.Thread(target=self._suspend_loop,
                                           name="ChipStreamSuspender",
                                           daemon=True)
        self._suspender.start()

    def resume(self):
        """Resume the jobs paused with :meth:`pause`"""
        with self._suspend_lock:
            self._paused.clear()
            for proc in self._suspended.values():
                try:
                    proc.resume()
                except (psutil.NoSuchProcess, psutil.ZombieProcess,
                        psutil.AccessDenied):
                    pass
            self._suspended.clear()
        if self._suspender is not None:
            self._suspender.join()
            self._suspender = None

    def _suspend_children(self):
        """Suspend all child processes that are not suspended yet"""
        with self._suspend_lock:
            if not self._paused.is_set():
                return
            for child in psutil.Process().children(recursive=True):
                if child.pid not in self._suspended:
                    try:
                        child.suspend()
                    except (psutil.NoSuchProcess, psutil.ZombieProcess,
                            psutil.AccessDenied):
                        continue
                    self._suspended[child.pid] = child

    def _suspend_loop(self):
        """Suspend new child processes while paused"""
        while self._paused.is_set():
            self._suspend_children()
            time.sleep(0.2)

    def join(self):
        if self._worker is not None and self._worker.is_alive():
            self._worker.join()

    def get_info(self, index):
        try:
            runner = self.get_runner(index)
            if runner is None:
                return "No job information available."
            if runner.state == "error":
                return str(runner.error_tb)
            elif runner.state == "done":
                return fetch_dcnum_log_from_file(runner.job["path_out"])
            else:
                # Open currently running log
                return runner.path_log.read_text()
        except BaseException:
            # Fallback for debugging
            return traceback.format_exc()

    def get_paths_out(self):
        """Return output path list"""
        pin = self._path_in_list
        if self._path_out is None:
            pout = [pp[0].with_name(pp[0].stem + "_dcn.rtdc") for pp in pin]
        else:
            # Get common stem for all paths
            # First, check whether all input files are on the same anchor.
            anchors = {pp.anchor for pp, _ in self._path_in_list}
            if len(anchors) == 1:
                common_parent = self._path_in_list[0][0].parent
                for pp, _ in self._path_in_list[1:]:
                    for parent in pp.parents:
                        if common_parent.is_relative_to(parent):
                            common_parent = parent
                            break
                pout = []
                for pp, _ in self._path_in_list:
                    prel = pp.relative_to(common_parent)
                    prel_dcn = prel.with_name(prel.stem + "_dcn.rtdc")
                    pout.append(self._path_out / prel_dcn)
            else:
                # This is a very weird scenario on Windows. The user added
                # files from different drives. We have to remove the anchor
                # part and compute relative files with a placeholder for
                # the anchor.
                # TODO: Find a way to test this.
                pout = []
                for pp, _ in self._path_in_list:
                    # relative path to anchor
                    prel = pp.relative_to(pp.anchor)
                    # placeholder for anchor
                    anch = "".join([ch for ch in pp.anchor if ch.isalnum()])
                    pout.append(self._path_out / anch / prel)
        return pout

    def get_paths_in(self):
        """Return input path list"""
        return [pp[0] for pp in self._path_in_list]

    def get_runner(self, index):
        if index >= len(self._runner_list):
            return None
        else:
            return self._runner_list[index]

    def run_all_in_thread(self,
                          job_kwargs: dict | None = None,
                          callback_when_done: Callable | None = None):
        if job_kwargs is None:
            job_kwargs = {}
        self._worker = JobWorker(paths_in=self._path_in_list,
                                 paths_out=self.get_paths_out(),
                                 job_kwargs=job_kwargs,
                                 runners=self._runner_list,
                                 busy_lock=self.busy_lock,
                                 callback_when_done=callback_when_done,
                                 )
        self._worker.start()

    def set_output_path(self, path_out):
        if path_out is not None:
            path_out = pathlib.Path(path_out)
        self._path_out = path_out


class ErrorredRunner:
    """Convenience class replacing a high-level failed runner"""
    def __init__(self, error_tb):
        self.error_tb = error_tb
        self.state = "error"

    def get_status(self):
        return {"state": "error",
                "progress": 0}


class JobWorker(threading.Thread):
    def __init__(self,
                 paths_in: list[list[pathlib.Path | str]],
                 paths_out: list[list[pathlib.Path | str]],
                 job_kwargs: dict,
                 runners: list,
                 busy_lock: threading.Lock | None = None,
                 callback_when_done: Callable | None = None,
                 override: bool = False,
                 *args, **kwargs):
        """Thread for running the pipeline

        Parameters
        ----------
        paths_in:
            List of tuples (path, state) of the input data
        paths_out:
            List of output paths for each item in `paths_in`
        job_kwargs:
            List of keyword arguments for the DCNumJob instance
        runners:
            Empty list which is filled with runner instances
        busy_lock:
            This threading.Lock is locked during processing
        callback_when_done:
            Method called after processing
        override: bool
            Whether to override the output file if it already exists.
            This does not override files that already have the correct
            pipeline identifiers.
        """
        super().__init__(*args, **kwargs)
        self.paths_in = paths_in
        self.paths_out = paths_out
        self.jobs = []
        self.runners = runners
        self.job_kwargs = job_kwargs
        self.busy_lock = busy_lock or threading.Lock()
        self.callback_when_done = callback_when_done
        self.override = override

    def run(self):
        with self.busy_lock:
            self.runners.clear()
            # reset all job states
            [pp.__setitem__(1, "created") for pp in self.paths_in]
            # run jobs
            for ii, (pp, _) in enumerate(self.paths_in):
                try:
                    self.run_job(path_in=pp, path_out=self.paths_out[ii])
                except BaseException:
                    # Create a dummy error runner
                    self.runners.append(ErrorredRunner(traceback.format_exc()))
                # write final state to path list
                runner = self.runners[ii]
                self.paths_in[ii][1] = runner.get_status()["state"]
        if self.callback_when_done is not None:
            self.callback_when_done()

    def run_job(self, path_in, path_out):
        job_kwargs = copy.deepcopy(self.job_kwargs)
        # We are using the 'sparsemed' background algorithm by default,
        # and we would like to perform flickering correction if necessary
        # (unless the user specified it explicitly).
        bg_kwargs = job_kwargs.setdefault("background_kwargs", {})
        if "offset_correction" not in bg_kwargs:
            with dcnum.read.HDF5Data(path_in) as hd:
                bg_kwargs["offset_correction"] = \
                    dcnum.read.detect_flickering(hd)

        job = dclogic.DCNumPipelineJob(path_in=path_in,
                                       path_out=path_out,
                                       **job_kwargs)
        self.jobs.append(job)
        # Make sure the job will run (This must be done after adding it
        # to the jobs list and before adding it to the runners list)
        job.validate()
        with dclogic.DCNumJobRunner(job) as runner:
            self.runners.append(runner)
            # We might encounter a scenario in which the output file
            # already exists. If we call `runner.run` in this case,
            # then the runner will raise a FileExistsError. There
            # are several ways to deal with this situation.
            path_out = job["path_out"]
            if path_out.exists():
                # If the pipeline ID hash of the output file matches
                # that of the input file, then we simply skip the run.
                try:
                    with h5py.File(path_out) as h5:
                        hash_act = h5.attrs.get("pipeline:dcnum hash")
                        if hash_act == runner.pphash:
                            # We have already processed this file.
                            runner.state = "done"
                            return
                except BaseException:
                    warnings.warn(f"Could not extract pipeline"
                                  f"identifier from '{path_out}'!")
                # If we are here, it means that the pipeline ID hash
                # did not match. We now have the chance to remove the
                # output file.
                if self.override:
                    path_out.unlink()
            # Run the pipeline, catching any errors the runner doesn't.
            runner.run()
        return runner


@lru_cache(maxsize=10000)
def fetch_dcnum_log_from_file(path):
    with dcnum.read.HDF5Data(path) as hd:
        logs = sorted(hd.logs.keys())
        logs = [ll for ll in logs if ll.startswith("dcnum-log-")]
        return "\n".join(hd.logs[logs[-1]])
