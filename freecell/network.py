import asynchat
import asyncore
import json
import socket
import threading
import time
import traceback

from events import *

# only add to event queue
# all receiving is done by FreeCellGame acquiring the lock
# must set source="networking" attribute
class FreeCellNetworking(asynchat.async_chat):
    def __init__(self, event_queue, shutdown_event, host="localhost", port=11982):
        asynchat.async_chat.__init__(self)
        self.event_queue = event_queue
        self.set_terminator("\r\n")
        self.buffer = []
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((host, port))
        self.lock = threading.Lock()
        self.shutdown_event = shutdown_event
        self.state = "connecting"

    def run(self):
        self.shutdown_event.wait()
        while self.shutdown_event.is_set():
            with self.lock:
                asyncore.loop(timeout=.1, count=1)
        self.close_when_done()

    def collect_incoming_data(self, data):
        self.buffer.append(data)

    def found_terminator(self):
        message = json.loads("".join(self.buffer))
        if "event" in message:
            self.create_event(message)
        else:
            print "Non-event message received"

        self.buffer = []

    def handle_connect(self):
        self.state = "connected"
        self.event_queue.put(MessageEvent(level="networking", message="Connected"))
        self.send_json({"event":"connect", "version": 1.2})

    def handle_error(self):
        traceback.print_exc()
        time.sleep(10)
        self.event_queue.put(MessageEvent(level="networking", message="Connection Refused"))
        self.event_queue.put(QuitEvent(unused=True))
        self.state = "refused"
        self.close()

    def create_event(self, message):
        if "event" in message:
            if message["event"] == "seed":
                self.event_queue.put(SeedEvent(seed=message["seed"]))
            if message["event"] == "stats":
                if message["won"]:
                    self.event_queue.put(MessageEvent(level="", message="Player %s has WON after %d seconds, %d moves, %d undos." % (message["id"], message["time"], message["moves"], message["undos"])))
                else:
                    self.event_queue.put(MessageEvent(level="", message="Player %s has conceded after %d seconds, %d moves, %d undos." % (message["id"], message["time"], message["moves"], message["undos"])))

    def send_event(self, event):
        with self.lock:
            if isinstance(event, Stats):
                self.send_json({'event':'stats', 'seed':event.seed, 'time':event.time, 'moves':event.moves, 'undos':event.undos, 'won':event.won})

    def send_json(self, object):
        self.push(json.dumps(object)+"\r\n")
