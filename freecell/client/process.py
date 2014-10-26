class Process(object):
    def __init__(self):
        self.state = "uninitialized"
        self.child = None

    def on_init(self):
        self.state = "running"

    def on_update(self, elapsed_time):
        pass

    def on_success(self):
        pass

    def on_fail(self):
        pass

    def on_stop(self):
        pass

    def succeed(self):
        self.state = "succeeded"

    def fail(self):
        self.state = "failed"

    def pause(self):
        self.state = "paused"

    def unpause(self):
        self.state = "running"

    def stop(self):
        self.state = "stop"

    def is_alive(self):
        return self.state == "running" or self.state == "paused"

    def is_dead(self):
        return self.state == "succeeded" or self.state == "failed" or self.state == "stopped"

    def is_removed(self):
        return self.state == "removed"

    def is_paused(self):
        return self.state == "paused"

    def attach_child(self, child):
        self.child = child

    def set_state(self, state):
        self.state = state

class ProcessManager(object):
    def __init__(self):
        self.processes = []
        """:type : list[Process]"""

    def update(self, elapsed_time):
        successes = 0
        fails = 0
        removed_processes = []
        for index in range(len(self.processes)):
            process = self.processes[index]

            if process.state == "uninitialized":
                process.on_init()

            if process.state == "running":
                process.on_update(elapsed_time)

            if process.is_dead():
                if process.state == "succeeded":
                    if process.child is not None:
                        self.attach_process(process.child)
                    else:
                        successes += 1

                elif process.state == "failed":
                    process.on_fail()
                    fails += 1

                elif process.state == "stopped":
                    process.on_stop()
                    fails += 1
                removed_processes.append(process)

        for process in removed_processes:
            self.processes.remove(process)


    def attach_process(self, process):
        pass

    def abort_all_processes(self, immediate):
        pass

class DelayProcess(Process):
    def __init__(self, delay_time):
        super(DelayProcess, self).__init__()
        self.delay_time = delay_time
        self.elapsed_time = 0

    def on_update(self, elapsed_time):
        self.elapsed_time += elapsed_time

        if self.elapsed_time > self.delay_time:
            self.succeed()