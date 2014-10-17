import random
import threading
import time

from events import *

from network import FreeCellNetworking

class FreeCellGame(object):
    def __init__(self, event_queue, logic, gui, seed=None, debug=False, networking=False):
        """
        :param Queue.Queue event_queue: Event Queue
        :param FreeCellLogic logic: Logic
        :param FreeCellGUI gui: GUI
        :param int seed: Seed
        :param bool debug: Debug enabled
        :param bool networking: Networking enabled
        """
        self.event_queue = event_queue
        self.logic = logic
        self.gui = gui
        self.gui.set_screen("intro")
        self.stats = None
        self.debug = debug
        self.networking = None
        self.shutdown_event = threading.Event()
        self.state = ""
        if networking:
            self.networking = FreeCellNetworking(self.event_queue, self.shutdown_event)
            threading.Thread(target=self.networking.run).start()
        else:
            if seed is None:
                self.set_seed(random.randint(0, 0xFFFFFFFF))
            else:
                self.set_seed(seed)

    def start(self, stdscr):

        self.shutdown_event.set()
        self.gui.start(stdscr)
        self.game_loop()

    def set_seed(self, seed):
        self.state = "seeded"
        self.seed = seed
        self.logic.load_seed(self.seed)
        self.gui.set_screen("game")

    def game_loop(self):
        if self.debug:
            from pydevd import pydevd
            from debug import DEBUG_HOST, DEBUG_PORT
            pydevd.settrace(DEBUG_HOST, port=DEBUG_PORT, suspend=False)

        self.gui.render()
        while self.shutdown_event.is_set():
            try:
                self.gui.get_input()
                self.process_event()
            except KeyboardInterrupt:
                while not self.event_queue.empty():
                    self.event_queue.get()
                self.event_queue.put(FinishEvent(won=False))
                self.process_event()

    def process_event(self):
        while not self.event_queue.empty():
            event = self.event_queue.get_nowait()

            if self.networking is not None:
                if hasattr(event, "origin") and event.origin != "networking":
                    self.networking.send_event(event)
                if isinstance(event, Stats):
                    self.networking.send_event(event)

            if isinstance(event, (InputEvent, MessageEvent)):
                self.gui.handle_event(event)
            elif isinstance(event, (MoveEvent, MoveCompleteEvent)):
                self.logic.handle_event(event) # .05s sleep before move UNLESS triggered by user (immediate=True, or something like that)
            elif isinstance(event, SeedEvent):
                self.set_seed(event.seed)
            elif isinstance(event, FinishEvent):
                self.stats = Stats(seed=self.seed, time=time.time()-self.logic.start, moves=self.logic.moves, undos=self.logic.undos, won=self.logic.is_solved())
                self.event_queue.put(self.stats)
                self.event_queue.put(QuitEvent(unused=True))
            elif isinstance(event, QuitEvent):
                self.quit(event)

            self.gui.render()

    def quit(self, event):
        self.shutdown_event.clear()
