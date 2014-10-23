import random

import events

from events import *
from loginserver import LoginWrapper
from network import FreecellServer

from ..shared.version import VERSION

class Competitor(object):
    def __init__(self, connection):
        """
        :param network.FreecellConnection connection: Connection
        """
        self.connection = connection

    def send(self, event):
        self.connection.send_json(event)

# last until everyone finishes seed or quits
class CompetitionServer(object):
    def __init__(self, host, port):
        self.event_dispatch = events.event_dispatch
        self.competitors = {}
        self.logins = {}
        self.shutdown_event = threading.Event()
        self.networking = FreecellServer(host, port)
        threading.Thread(target=self.networking.run, args=(self.shutdown_event,)).start()
        self.current_seed = random.randint(1, 0xFFFFFFFF)

    def start(self):
        self.event_dispatch.register(self.competitor_join, ["JoinEvent"])
        self.event_dispatch.register(self.competitor_auth, ["AuthEvent"])
        self.event_dispatch.register(self.competitor_quit, ["QuitEvent"])
        self.event_dispatch.register(self.competitor_win, ["WinEvent"])
        self.event_dispatch.register(self.send_seed, ["SeedRequestEvent"])
        MAX_FPS = 30
        S_PER_FRAME = 1.0/MAX_FPS
        self.shutdown_event.set()
        while self.shutdown_event.is_set():
            start = time.time()
            try:
                self.event_dispatch.update(S_PER_FRAME)
                elapsed = time.time() - start
                if elapsed < S_PER_FRAME:
                    time.sleep(S_PER_FRAME-elapsed)
            except KeyboardInterrupt:
                print "Keyboard Interrupt"
                self.shutdown_event.clear()

    def competitor_win(self, event):
        print "WIN: %s" % event.id
        if event.won:
            self.current_seed = random.randint(1, 0xFFFFFFFF)
        for competitor in self.competitors.values():
            #WinEvent = namedtuple('WinEvent', ['id', 'seed', 'time', 'moves', 'undos', 'won'])
            competitor.send({"event":"stats", "id":event.id, "seed":event.seed, "time":event.time, "moves":event.moves, "undos":event.undos, "won":event.won})

    def competitor_join(self, event):
        print "JOIN: %s v%.2f" % (event.id, event.version)

        if event.version == VERSION:
            self.logins[event.id] = LoginWrapper(event.object)
        else:
            event.object.send_json({"event":"badversion", "min_version":VERSION})

    def competitor_auth(self, event):
        print "AUTH"
        competitor = Competitor(event.connection)
        self.competitors[event.id] = competitor
        del self.logins[event.id]

    def send_seed(self, event):
        print "SEND SEED"
        if event.id in self.competitors:
            self.competitors[event.id].send({"event":"seed", "seed":self.current_seed})

    def competitor_quit(self, event):
        print "QUIT: %s %s" % (event.id, event.reason)
        if event.id in self.competitors:
            del self.competitors[event.id]
