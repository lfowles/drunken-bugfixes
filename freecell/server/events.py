import Queue
import threading
import time

from collections import defaultdict, namedtuple

# TODO: event prototypes in shared, then a ServerEvent type object that will create event objects

JoinEvent = namedtuple('JoinEvent', ['id', 'version', 'object'])
QuitEvent = namedtuple('QuitEvent', ['id', 'reason'])
WinEvent = namedtuple('WinEvent', ['id', 'seed', 'time', 'moves', 'undos', 'won'])
SeedEvent = namedtuple('SeedEvent', ['seed'])
MessageEvent = namedtuple('MessageEvent', ['level', 'message'])

class EventDispatch(object):
    def __init__(self):
        self.queue = Queue.PriorityQueue()
        self.registered = defaultdict(list)
        """:type : defaultdict[str, list]"""
        self.lock = threading.Lock()

    def register(self, callback, event_types):
        """
        :param callable callback: Callback for event types
        :param list[str] event_types: List of event types (as strings)
        """
        with self.lock:
            for event_type in event_types:
                if callback not in self.registered[event_type]:
                    self.registered[event_type].append(callback)

    def unregister(self, callback, event_types):
        """
        :param callable callback: Callback for event types
        :param list[str] event_types: List of event types (as strings)
        :rtype bool:
        """
        with self.lock:
            for event_type in event_types:
                if callback in self.registered[event_type]:
                    self.registered[event_type].remove(callback)

    def send(self, event, priority=5):
        """
        :param namedtuple event: Event
        """
        self.queue.put((priority, time.time(), event))

    def update(self, max_time):
        start = time.time()
        while not self.queue.empty():
            item = self.queue.get_nowait()
            event = item[2]
            for callback in self.registered[type(event).__name__]:
                callback(event)
            self.queue.task_done()

            if time.time() - start >= max_time:
                return False
        else:
            return True

event_dispatch = EventDispatch()