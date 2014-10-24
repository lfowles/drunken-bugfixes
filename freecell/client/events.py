import Queue
import threading
import time

from collections import defaultdict, namedtuple

InputEvent = namedtuple('InputEvent', ['key'])
MoveEvent = namedtuple('MoveEvent', ['source', 'dest', 'num'])
MoveCompleteEvent = namedtuple('MoveCompleteEvent', ['unused'])
FinishEvent = namedtuple('FinishEvent', ['won'])
QuitEvent = namedtuple('QuitEvent', ['message'])
MessageEvent = namedtuple('MessageEvent', ['level', 'message'])
SeedEvent = namedtuple('SeedEvent', ['seed'])
Stats = namedtuple('Stats', ['seed', 'time', 'moves', 'undos', 'won'])
BadVersionEvent = namedtuple('BadVersionEvent', ['min_version'])
LoginEvent = namedtuple('LoginEvent', ['username'])
UnknownUserEvent = namedtuple('UnknownUserEvent', ['username'])
NonceEvent = namedtuple('NonceEvent', ['nonce', 'salt'])
TokenHashEvent = namedtuple('TokenHashEvent', ['username', 'nonce_hash'])
LoggedInEvent = namedtuple('LoggedInEvent', ['username'])
LoginFailedEvent = namedtuple('LoginFailedEvent', ['username'])
ScreenChangeEvent = namedtuple('ScreenChangeEvent', ['screen'])
RegisterEvent = namedtuple('RegisterEvent', ['username'])
NameTakenEvent = namedtuple('NameTakenEvent', ['username'])
LoginTokenEvent = namedtuple('LoginTokenEvent', ['username', 'token'])
SeedRequestEvent = namedtuple('SeedRequestEvent', [])
InputFlowEvent = namedtuple('InputFlowEvent', ['buffer', 'pause'])
LeaderEvent = namedtuple('LeaderEvent', ['username', 'moves', 'time', 'undos'])

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