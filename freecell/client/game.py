import Queue
import random

import events
from events import *
from gui import FreeCellGUI
from logic import FreeCellLogic
from network import FreeCellNetworking


class FreeCellGame(object):
    def __init__(self, seed=None, debug=False, networking=False):
        """
        :param int seed: Seed
        :param bool debug: Debug enabled
        :param bool networking: Networking enabled
        """
        self.event_dispatch = events.event_dispatch
        self.logic = FreeCellLogic()
        self.gui = FreeCellGUI(self.logic)
        self.input = self.gui.get_input()
        self.stats = None
        self.seed = None
        self.debug = debug
        self.networking = None
        self.shutdown_event = threading.Event()
        self.quit_message = None
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
        if self.networking is not None:
            self.event_dispatch.send(ScreenChangeEvent(screen="login"))

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
        self.event_dispatch.send(ScreenChangeEvent(screen="game"))

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
        MAX_FPS = 30
        S_PER_FRAME = 1.0/MAX_FPS
        while self.shutdown_event.is_set():
            start = time.time()
            try:
                self.event_dispatch.update(.1)
                # TODO: have GUI only render on changed screen
                self.gui.render()
                elapsed = time.time() - start
                if elapsed < S_PER_FRAME:
                    time.sleep(S_PER_FRAME-elapsed)
            except KeyboardInterrupt:
                self.event_dispatch.send(FinishEvent(won=False), priority=1)


    def finish(self, event):
        if self.seed is not None:
            self.stats = Stats(seed=self.seed, time=time.time()-self.logic.start_time, moves=self.logic.moves, undos=self.logic.undos, won=self.logic.is_solved())
            self.event_dispatch.send(self.stats)
            if self.stats.won:
                message = "You won!"
            else:
                message = "Better luck next time."
        else:
            message = ""
        self.event_dispatch.send(QuitEvent(message=message))


    def quit(self, event):
        self.quit_message = event.message
        self.shutdown_event.clear()
