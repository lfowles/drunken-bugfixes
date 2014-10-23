import json
import keyword
import Queue
import threading
import time

from collections import defaultdict

event_prototypes = [
    {'event':'JoinEvent', 'version':float, 'object':None},
    {'event':'AuthEvent', 'connection':None},
    {'event':'WinEvent', 'seed':int, 'time':float, 'moves':int, 'undos':int, 'won':bool},
    {'event':'QuitEvent', 'reason':basestring},

    {'event':'LoginEvent', 'username':basestring},
    {'event':'RegisterEvent', 'username':basestring},
    {'event':'NameTakenEvent', 'username':basestring},
    {'event':'LoginTokenEvent', 'username':basestring, 'token':basestring},
    {'event':'TokenHashEvent', 'username':basestring, 'nonce_hash':basestring},

    {'event':'SeedRequestEvent'},
    ]

events = {}
""":type : dict[str, Event] """

# Change event to event_type
class Event(object):
    prototype = {}
    event = None
    def __init__(self, **kwargs):
        if "event" in kwargs:
            if self.event != kwargs["event"]:
                raise TypeError("Unable to create '%s' object from '%s' data" % (self.event, kwargs["event"]))
            del kwargs["event"]

        if not sorted(kwargs.keys()) == sorted(self.prototype.keys()):
            raise TypeError('Required args: %s, Provided args: %s' %
                            (", ".join(self.prototype.keys()), ", ".join(kwargs.keys()))
                            )

        for key, arg_type in self.prototype.items():
            if arg_type is not None:
                if not isinstance(kwargs[key], arg_type):
                    raise TypeError("Arg '%s' must be of type %s" % (key, arg_type.__name__))

        self.__dict__.update(kwargs)

    def serialize(self):
        ser_dict = {key: self.__dict__[key] for key in self.prototype.keys()}
        ser_dict["event"] = self.event
        return json.dumps(ser_dict)

def server_event_creator(event_prototype):
    assert "event" in event_prototype
    for attr in event_prototype:
        assert not keyword.iskeyword(attr)
        assert attr not in ["prototype", "id", "origin"]

    event_type = event_prototype["event"]
    assert event_type not in events

    # Add server specific args
    #event_prototype.update({"id":str, "origin":str})
    event_prototype.update({"id":str})
    del event_prototype["event"] # remove "event" from the prototype, the class already knows what type it is
    class_dict = {"prototype": event_prototype, "event":event_type}
    class_dict.update(event_prototype)

    Cls = type(event_type, (Event,), class_dict)

    events[event_type] = Cls

def make_event(event_type, **kwargs):
    Cls = events[event_type]
    return Cls(**kwargs)

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

for event in event_prototypes:
    server_event_creator(event)

event_dispatch = EventDispatch()