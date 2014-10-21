import random

import events

from events import *
from network import FreecellServer

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
        self.shutdown_event = threading.Event()
        self.networking = FreecellServer(host, port)
        threading.Thread(target=self.networking.run, args=(self.shutdown_event,)).start()
        self.current_seed = random.randint(1, 0xFFFFFFFF)

    def start(self):
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

    def handle_event(self, event):
        if isinstance(event, JoinEvent):
            self.competitor_join(event)

        elif isinstance(event, QuitEvent):
            self.competitor_quit(event)

        elif isinstance(event, WinEvent):
            self.competitor_win(event)

    def competitor_win(self, event):
        print "WIN: %s" % event.id
        for competitor in self.competitors.values():
            #WinEvent = namedtuple('WinEvent', ['id', 'seed', 'time', 'moves', 'undos', 'won'])
            competitor.send({"event":"stats", "id":event.id, "seed":event.seed, "time":event.time, "moves":event.moves, "undos":event.undos, "won":event.won})

    def competitor_join(self, event):
        print "JOIN: %s v%.2f" % (event.id, event.version)
        self.competitors[event.id] = Competitor(event.object)
        event.object.send({"event":"seed", "seed":self.current_seed})

    def competitor_quit(self, event):
        print "QUIT: %s %s" % (event.id, event.reason)
        if event.id in self.competitors:
            del self.competitors[event.id]
