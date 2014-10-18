import Queue
import random
import threading
import time

import events
from events import *

from gui import FreeCellGUI
from logic import FreeCellLogic
from network import FreeCellNetworking

class FreeCellGame(object):
    def __init__(self, seed=None, debug=False, networking=False):
        """
        :param Queue.Queue event_queue: Event Queue
        :param FreeCellLogic logic: Logic
        :param FreeCellGUI gui: GUI
        :param int seed: Seed
        :param bool debug: Debug enabled
        :param bool networking: Networking enabled
        """
        self.event_dispatch = events.event_dispatch
        self.logic = FreeCellLogic()
        self.gui = FreeCellGUI(self.logic)
        self.input = self.gui.get_input()
        self.stats = None
        self.debug = debug
        self.networking = None
        self.shutdown_event = threading.Event()
        self.state = ""
        self.threads = []
        input_thread = threading.Thread(target=self.input.run)
        input_thread.daemon = True
        self.threads.append(input_thread)
        if networking:
            self.networking = FreeCellNetworking()
            self.threads.append(threading.Thread(target=self.networking.run, args=(self.shutdown_event,)))
        else:
            event = SeedEvent(seed=seed or random.randint(0, 0xFFFFFFFF))
            self.event_dispatch.send(event)

    def start(self, stdscr):
        if self.debug:
            from pydevd import pydevd
            from debug import DEBUG_HOST, DEBUG_PORT
            pydevd.settrace(DEBUG_HOST, port=DEBUG_PORT, suspend=False)

        self.event_dispatch.register(self.finish, ["FinishEvent"])
        self.event_dispatch.register(self.quit, ["QuitEvent"])
        self.event_dispatch.register(self.set_seed, ["SeedEvent"])
        self.event_dispatch.register(self.handle_input, ["InputEvent"])
        for thread in self.threads:
            thread.start()
        self.shutdown_event.set()
        self.logic.start()
        self.input.start(stdscr)
        self.gui.start(stdscr)
        self.game_loop()

    def set_seed(self, event):
        self.state = "seeded"
        self.seed = event.seed
        self.logic.load_seed(self.seed)
        self.gui.set_screen("game")

    def handle_input(self, event):
        if event.key == ord('?'):
            width = 38
            height = 7
            y = 4
            x = 3
            import curses
            win = curses.newwin(height, width, y, x)
            self.gui.set_screen("help")
            self.gui.screens[self.gui.screen].set_window(win)
        elif event.key == ord('Q'):
            self.event_dispatch.send(FinishEvent(won=False))

    def game_loop(self):
        self.gui.render()

        while self.shutdown_event.is_set():
            try:
                self.input.get_input()
                self.gui.render()
                self.event_dispatch.update(.1)
            except KeyboardInterrupt:
                self.event_dispatch.send(FinishEvent(won=False), priority=1)

    def process_event(self):

            if self.networking is not None:
                if hasattr(event, "origin") and event.origin != "networking":
                    self.networking.send_event(event)
                if isinstance(event, Stats):
                    self.networking.send_event(event)

    def finish(self, event):
        self.stats = Stats(seed=self.seed, time=time.time()-self.logic.start, moves=self.logic.moves, undos=self.logic.undos, won=self.logic.is_solved())
        self.event_dispatch.send(self.stats)
        self.event_dispatch.send(QuitEvent(unused=True))

    def quit(self, event):
        self.shutdown_event.clear()
