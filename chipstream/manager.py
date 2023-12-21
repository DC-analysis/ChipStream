import pathlib
import threading
import traceback
from typing import Dict, List
import warnings

import dcnum.read
from dcnum import logic as dclogic
import h5py


class JobStillRunningError(BaseException):
    pass


class ChipStreamJobManager:
    def __init__(self):
        self._path_list = []
        self._runner_list = []
        self._worker = None
        self.busy_lock = threading.Lock()

    def __getitem__(self, index):
        runner = self.get_runner(index)
        if runner is None:
            status = {"progress": 0,
                      "state": self._path_list[index][1],
                      }
        else:
            status = runner.get_status()
        status["path"] = str(self._path_list[index][0])
        return status

    def __len__(self):
        return len(self._path_list)

    @property
    def current_index(self):
        return None if not self._runner_list else len(self._runner_list) - 1

    def add_path(self, path):
        if not self.is_busy():
            # Only append paths if we are currently not busy
            self._path_list.append([path, "created"])

    def clear(self):
        """Clear all data"""
        self._path_list.clear()
        self._runner_list.clear()
        self._worker = None

    def is_busy(self):
        return self.busy_lock.locked()

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
                with dcnum.read.HDF5Data(runner.job["path_out"]) as hd:
                    logs = sorted(hd.logs.keys())
                    logs = [ll for ll in logs if ll.startswith("dcnum-log-")]
                    return "\n".join(hd.logs[logs[-1]])
            else:
                # Open currently running log
                return runner.path_log.read_text()
        except BaseException:
            # Fallback for debugging
            return traceback.format_exc()

    def get_runner(self, index):
        if index >= len(self._runner_list):
            return None
        else:
            return self._runner_list[index]

    def run_all_in_thread(self, job_kwargs=None, callback_when_done=None):
        if job_kwargs is None:
            job_kwargs = {}
        self._worker = JobWorker(paths=self._path_list,
                                 job_kwargs=job_kwargs,
                                 runners=self._runner_list,
                                 busy_lock=self.busy_lock,
                                 callback_when_done=callback_when_done,
                                 )
        self._worker.start()


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
                 paths: List[List[pathlib.Path | str]],
                 job_kwargs: Dict,
                 runners: List,
                 busy_lock: threading.Lock = None,
                 callback_when_done: callable = None,
                 override: bool = False,
                 *args, **kwargs):
        """Thread for running the pipeline

        Parameters
        ----------
        paths:
            List of input paths to process
        job_kwargs:
            List of keyword arguments for the DCNumJob instace
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
        super(JobWorker, self).__init__(*args, **kwargs)
        self.paths = paths
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
            [pp.__setitem__(1, "created") for pp in self.paths]
            # run jobs
            for ii, (pp, _) in enumerate(self.paths):
                try:
                    self.run_job(path_in=pp)
                except BaseException:
                    # Create a dummy error runner
                    self.runners.append(ErrorredRunner(traceback.format_exc()))
                # write final state to path list
                runner = self.runners[ii]
                self.paths[ii][1] = runner.get_status()["state"]
        if self.callback_when_done is not None:
            self.callback_when_done()

    def run_job(self, path_in):
        job = dclogic.DCNumPipelineJob(path_in=path_in, **self.job_kwargs)
        self.jobs.append(job)
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
