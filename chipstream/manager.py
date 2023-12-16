import threading

from dcnum import logic as dclogic


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

    def is_busy(self):
        return self.busy_lock.locked()

    def get_runner(self, index):
        if index >= len(self._runner_list):
            return None
        else:
            return self._runner_list[index]

    def run_all_in_thread(self, job_kwargs=None):
        if job_kwargs is None:
            job_kwargs = {}
        self._worker = JobWorker(paths=self._path_list,
                                 job_kwargs=job_kwargs,
                                 runners=self._runner_list,
                                 busy_lock=self.busy_lock)
        self._worker.start()


class JobWorker(threading.Thread):
    def __init__(self, paths, job_kwargs, runners, busy_lock, *args, **kwargs):
        super(JobWorker, self).__init__(*args, **kwargs)
        self.paths = paths
        self.jobs = []
        self.runners = runners
        self.job_kwargs = job_kwargs
        self.busy_lock = busy_lock

    def run(self):
        with self.busy_lock:
            for ii, (pp, _) in enumerate(self.paths):
                job = dclogic.DCNumPipelineJob(path_in=pp, **self.job_kwargs)
                self.jobs.append(job)
                with dclogic.DCNumJobRunner(job) as runner:
                    self.runners.append(runner)
                    runner.run()
                # write final state to path list
                self.paths[ii][1] = runner.get_status()["state"]
