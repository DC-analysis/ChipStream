import threading

from dcnum import logic as dclogic


class JobStillRunningError(BaseException):
    pass


class ChipStreamJobManager(threading.Thread):
    def __init__(self, *args, **kwargs):
        super(ChipStreamJobManager, self).__init__(*args, **kwargs)
        self.path_list = []
        self.current_index = None
        self.current_job = None
        self.current_runner = None

    def __getitem__(self, index):
        if index == self.current_index:
            status = self.current_runner.get_status()
        else:
            path, state = self.path_list[index]
            status = {"progress": 1 if state == "done" else 0,
                      "state": state,
                      }
        status["path"] = str(self.path_list[index][0])
        return status

    def __len__(self):
        return len(self.path_list)

    def add_path(self, path):
        self.path_list.append([path, "created"])

    def run_path(self, index, /, **dckwargs):
        if self.current_runner is not None:
            status = self.current_runner.get_status()
            if status["state"] not in ["error", "done"]:
                raise JobStillRunningError(
                    f"Cannot start job {index}, because job "
                    f"{self.current_index} is still running!")
            else:
                self.current_runner.join()
                self.path_list[index][1] = status["state"]
            self.current_index = None
            self.current_job = None
            self.current_runner = None

        self.current_job = dclogic.DCNumPipelineJob(
            path_in=self.path_list[index][0],
            **dckwargs)
        self.current_runner = dclogic.DCNumJobRunner(self.current_job)
        self.current_runner.start()
        self.current_index = index

    def run(self):
        self.run_path(0)
        self.current_runner.join()
