import asynchat
import asyncore
import json
import socket
import threading
import time
import traceback

import events

from events import *

# only add to event queue
# all receiving is done by FreeCellGame acquiring the lock
# must set source="networking" attribute
class FreeCellNetworking(asynchat.async_chat):
    def __init__(self, host="knitwithlogic.com", port=11982):
        asynchat.async_chat.__init__(self)
        self.event_dispatch = events.event_dispatch
        self.set_terminator("\r\n")
        self.buffer = []
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addr = (host, port)
        self.connect(self.addr)
        self.lock = threading.Lock()
        self.state = "connecting"

    def run(self, shutdown_event):
        shutdown_event.wait()
        self.event_dispatch.register(self.send_event, ["Stats"])
        while shutdown_event.is_set():
            with self.lock:
                asyncore.loop(timeout=.1, count=1)
        self.event_dispatch.unregister(self.send_event, ["Stats"])
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
        self.event_dispatch.send(MessageEvent(level="networking", message="Connected"))
        self.send_json({"event":"connect", "version": 1.2})

    def handle_error(self):
        traceback.print_exc()
        self.event_dispatch.send(QuitEvent(message="Connection refused to %s:%d" % self.addr))
        self.state = "refused"
        self.close()

    def create_event(self, message):
        if "event" in message:
            if message["event"] == "seed":
                self.event_dispatch.send(SeedEvent(seed=message["seed"]))
            if message["event"] == "stats":
                if message["won"]:
                    self.event_dispatch.send(MessageEvent(level="", message="Player %s has WON after %d seconds, %d moves, %d undos." % (message["id"], message["time"], message["moves"], message["undos"])))
                else:
                    self.event_dispatch.send(MessageEvent(level="", message="Player %s has conceded after %d seconds, %d moves, %d undos." % (message["id"], message["time"], message["moves"], message["undos"])))

    def send_event(self, event):
        with self.lock:
            if isinstance(event, Stats):
                self.send_json({'event':'stats', 'seed':event.seed, 'time':event.time, 'moves':event.moves, 'undos':event.undos, 'won':event.won})

    def send_json(self, object):
        if self.state == "connected":
            self.push(json.dumps(object)+"\r\n")
