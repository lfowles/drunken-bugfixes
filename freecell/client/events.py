import Queue
import threading
import time
import weakref

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

Callback = namedtuple('Callback', ['fn', 'obj'])

class EventDispatch(object):
    def __init__(self):
        self.queue = Queue.PriorityQueue()
        self.registered = defaultdict(set)
        """:type : defaultdict[str, list]"""
        self.lock = threading.Lock()

    def make_callback(self, callback):
        try:
            callback = Callback(fn=weakref.ref(callback.__func__), obj=weakref.ref(callback.__self__))
        except AttributeError:
            callback = Callback(fn=weakref.ref(callback.__func__), obj=None)
        return callback

    def register(self, callback, event_types):
        """
        :param callable callback: Callback for event types
        :param list[str] event_types: List of event types (as strings)
        """
        with self.lock:
            callback = self.make_callback(callback)
            for event_type in event_types:
                self.registered[event_type].add(callback)

    def unregister(self, callback, event_types):
        """
        :param callable callback: Callback for event types
        :param list[str] event_types: List of event types (as strings)
        :rtype bool:
        """
        with self.lock:
            callback = self.make_callback(callback)
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
            cleanup_callbacks = []
            for callback in set(self.registered[type(event).__name__]):
                fn = callback.fn()
                if fn is None:
                    cleanup_callbacks.append(callback)
                    continue

                if callback.obj is None:
                    fn(event)
                else:
                    obj = callback.obj()
                    if obj is None:
                        cleanup_callbacks.append(callback)
                        continue
                    fn(obj, event)

            for callback in cleanup_callbacks:
                self.registered[type(event).__name__].remove(callback)

            self.queue.task_done()

            if time.time() - start >= max_time:
                return False
        else:
            return True

event_dispatch = EventDispatch()