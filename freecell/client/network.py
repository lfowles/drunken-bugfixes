import asynchat
import asyncore
import json
import socket
import time
import traceback

from ..shared.version import VERSION

from events import *

# only add to event queue
# all receiving is done by FreeCellGame acquiring the lock
# must set source="networking" attribute
import events


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
        self.event_dispatch.register(self.send_event, ["Stats", "LoginEvent", "RegisterEvent", "TokenHashEvent", "SeedRequestEvent"])
        while shutdown_event.is_set():
            MAX_FPS = 30
            S_PER_FRAME = 1.0/MAX_FPS
            start = time.time()

            with self.lock:
                asyncore.loop(timeout=0, count=1)

            elapsed = time.time()-start
            if elapsed < S_PER_FRAME:
                time.sleep(S_PER_FRAME-elapsed)
        self.event_dispatch.unregister(self.send_event, ["Stats", "LoginEvent", "RegisterEvent", "TokenHashEvent", "SeedRequestEvent"])
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
        self.send_json({"event":"connect", "version": VERSION})

    def handle_error(self):
        traceback.print_exc()
        self.event_dispatch.send(QuitEvent(message="Connection refused to %s:%d" % self.addr))
        self.state = "refused"
        self.close()

    def create_event(self, message):
        if "event" in message:
            if message["event"] == "seed":
                self.event_dispatch.send(SeedEvent(seed=message["seed"]))
            elif message["event"] == "stats":
                if message["won"]:
                    self.event_dispatch.send(MessageEvent(level="", message="Player %s has WON after %d seconds, %d moves, %d undos." % (message["id"], message["time"], message["moves"], message["undos"])))
                else:
                    self.event_dispatch.send(MessageEvent(level="", message="Player %s has conceded after %d seconds, %d moves, %d undos." % (message["id"], message["time"], message["moves"], message["undos"])))
            elif message["event"] == "badversion":
                self.event_dispatch.send(QuitEvent(message="Client version %s required" % message["min_version"]))
            elif message["event"] == "nonce":
                self.event_dispatch.send(NonceEvent(nonce=message["nonce"], salt=message["salt"]))
            elif message["event"] == "unknownuser":
                self.event_dispatch.send(UnknownUserEvent(username=message["username"]))
            elif message["event"] == "nametaken":
                self.event_dispatch.send(NameTakenEvent(username=message["username"]))
            elif message["event"] == "logintoken":
                self.event_dispatch.send(LoginTokenEvent(username=message["username"], token=message["token"]))
            elif message["event"] == "loggedin":
                self.event_dispatch.send(LoggedInEvent(username=message["username"]))
            elif message["event"] == "loginfailed":
                self.event_dispatch.send(LoginFailedEvent(username=message["username"]))
            elif message["event"] == "leader":
                self.event_dispatch.send(LeaderEvent(username=message["username"], time=message["time"], moves=message["moves"], undos=message["undos"]))

    def send_event(self, event):
        with self.lock:
            #"LoginEvent", "RegisterEvent", "TokenHashEvent"
            if isinstance(event, Stats):
                self.send_json({'event':'stats', 'seed':event.seed, 'time':event.time, 'moves':event.moves, 'undos':event.undos, 'won':event.won})
            elif isinstance(event, LoginEvent):
                self.send_json({'event':'login', 'username':event.username})
            elif isinstance(event, RegisterEvent):
                self.send_json({'event':'register', 'username':event.username})
            elif isinstance(event, TokenHashEvent):
                self.send_json({'event':'tokenhash', 'username':event.username, 'nonce_hash':event.nonce_hash})
            elif isinstance(event, SeedRequestEvent):
                self.send_json({'event':'seedrequest'})

    def send_json(self, obj):
        if self.state == "connected":
            self.push(json.dumps(obj)+"\r\n")
