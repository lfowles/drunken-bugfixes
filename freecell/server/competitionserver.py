import json
from operator import attrgetter
import os.path
import threading
import time
import random

import events
from loginserver import LoginWrapper
from network import FreecellServer

from ..shared.version import VERSION

from collections import namedtuple
LeaderboardEntry = namedtuple('LeaderboardEntry', ['username', 'time', 'moves', 'undos'])

class Competitor(object):
    def __init__(self, connection, username):
        """
        :param network.FreecellConnection connection: Connection
        """
        self.connection = connection
        self.username = username

    def send(self, event):
        self.connection.send_json(event)

# last until everyone finishes seed or quits
class CompetitionServer(object):
    def __init__(self, host, port):
        self.event_dispatch = events.event_dispatch
        self.competitors = {}
        self.leaderboards = {}
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

        if os.path.isfile(os.path.expanduser("~/.freecell_leaderboards")):
            with open(os.path.expanduser("~/.freecell_leaderboards")) as leaderboard_file:
                self.leaderboards = json.load(leaderboard_file)

        if self.current_seed not in self.leaderboards:
            self.leaderboards[self.current_seed] = []

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
                with open(os.path.expanduser("~/.freecell_leaderboards"), "w") as leaderboard_file:
                    json.dump(self.leaderboards, leaderboard_file)
                print "Keyboard Interrupt"
                self.shutdown_event.clear()

    def competitor_win(self, event):
        print "WIN: %s" % event.id
        if event.won:
            self.current_seed = random.randint(1, 0xFFFFFFFF)
            if self.current_seed not in self.leaderboards:
                self.leaderboards[self.current_seed] = []

            if self.competitors[event.id].username not in [x.username for x in self.leaderboards[event.seed]]:
                self.leaderboards[event.seed].append(LeaderboardEntry(username=self.competitors[event.id].username, time=event.time, moves=event.moves, undos=event.undos))

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
        competitor = Competitor(event.connection, event.username)
        self.competitors[event.id] = competitor
        del self.logins[event.id]

    def send_seed(self, event):
        print "SEND SEED"
        if event.id in self.competitors:
            self.competitors[event.id].send({"event":"seed", "seed":self.current_seed})
            leaderboard = self.leaderboards[self.current_seed]
            leaderboard = sorted(leaderboard, key=attrgetter('time'))
            leaderboard = sorted(leaderboard, key=attrgetter('moves'))
            leaderboard = sorted(leaderboard, key=attrgetter('undos'), reverse=True)
            for leader in leaderboard[:1]:
                self.competitors[event.id].send({"event":"leader", "username":leader.username, "time":leader.time, "moves":leader.moves, "undos":leader.undos})

    def competitor_quit(self, event):
        print "QUIT: %s %s" % (event.id, event.reason)
        if event.id in self.competitors:
            del self.competitors[event.id]
