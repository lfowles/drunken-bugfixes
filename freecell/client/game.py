import curses
import Queue
import random

import events
from events import *
from logic import FreeCellLogic
from network import NetworkView
from input import CursesInput

from freecellgameview import FreecellGameView
from mainmenuview import MainMenuView

class FreeCellGame(object):
    def __init__(self, seed=None, debug=False, networking=False):
        """
        :param int seed: Seed
        :param bool debug: Debug enabled
        :param bool networking: Networking enabled
        """
        self.event_dispatch = events.event_dispatch
        self.logic = FreeCellLogic()
        self.curses_lock = threading.Lock()
        self.input = CursesInput(self.curses_lock)
        self.views = []
        self.stats = None
        self.seed = None
        self.debug = debug
        self.networking = None
        self.shutdown_event = threading.Event()
        self.quit_message = None
        self.state = ""
        self.threads = []
        self.username = "localuser"

        input_thread = threading.Thread(target=self.input.run)
        input_thread.daemon = True
        self.threads.append(input_thread)
        if networking:
            self.networking = NetworkView()
            self.threads.append(threading.Thread(target=self.networking.run, args=(self.shutdown_event,)))
        else:
            event = SeedEvent(seed=seed or random.randint(0, 0xFFFFFFFF))
            self.event_dispatch.send(event)

    def start(self, stdscr):
        if self.debug:
            try:
                from pydevd import pydevd
                from debug import DEBUG_HOST, DEBUG_PORT
                pydevd.settrace(DEBUG_HOST, port=DEBUG_PORT, suspend=False)
            except ImportError:
                pass # Can't debug if pydevd or debug don't exist, so whatever

        #if self.networking is not None:
        main_menu = MainMenuView(stdscr)
        main_menu.load()
        self.views.append(main_menu)
        if self.networking is not None:
            self.event_dispatch.register(self.state_change, ["LoggedInEvent"])

        self.event_dispatch.register(self.finish, ["FinishEvent"])
        self.event_dispatch.register(self.quit, ["QuitEvent"])
        self.event_dispatch.register(self.set_seed, ["SeedEvent"])
        self.event_dispatch.register(self.handle_input, ["InputEvent"])
        for thread in self.threads:
            thread.start()
        self.shutdown_event.set()
        self.logic.start()
        self.input.start(stdscr)
        self.curses_init()
        self.game_loop()

    def curses_init(self):
        with self.curses_lock:
            curses.curs_set(0)
            curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)

            # selected
            curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLUE)
            curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLUE)

            curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)

            # can automove
            curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_RED)
            curses.init_pair(6, curses.COLOR_CYAN, curses.COLOR_RED)

            # stacked correctly
            curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_GREEN)
            curses.init_pair(8, curses.COLOR_CYAN, curses.COLOR_GREEN)

    def state_change(self, event):
        if isinstance(event, LoggedInEvent):
            self.username = event.username
            self.event_dispatch.register(self.set_seed, ["SeedEvent"])
            self.event_dispatch.send(SeedRequestEvent())

        # TODO: register for WinEvent too

    def set_seed(self, event):
        self.state = "seeded"
        self.seed = event.seed
        self.logic.load_seed(self.seed)
        # View right now is only MainMenuView, so switch to FreecellHumanGameView
        # change window
        main_menu = self.views.pop()
        main_menu.unload()
        game_view = FreecellGameView(main_menu.window, self.username, self.logic.table, self.logic)
        game_view.load()
        self.views.append(game_view)

    def handle_input(self, event):
        if event.key == ord('?'):
            width = 38
            height = 7
            y = 4
            x = 3
            import curses
#            win = curses.newwin(height, width, y, x)
#            self.gui.set_screen("help")
#            self.gui.screens[self.gui.screen].set_window(win)
        elif event.key == ord('Q'):
            self.event_dispatch.send(FinishEvent(won=False))

    def game_loop(self):
        MAX_FPS = 30
        S_PER_FRAME = 1.0/MAX_FPS
        start = time.time()

        while self.shutdown_event.is_set():
            try:
                elapsed = time.time() - start
                start += elapsed

                self.event_dispatch.update(S_PER_FRAME)

                for view in self.views:
                    view.update(elapsed)
                for view in self.views:
                    if hasattr(view, 'window'):
                        with self.curses_lock:
                            # need to erase all windows needed :\ this will become an issue when I redo the help window
                            view.window.erase()
                            window_list = view.render(elapsed)
                            for window in window_list:
                                window.refresh()
                # Remake this to be
                # Views can contain UIs
                # init a mainmenuview on load
                # game.onupdate which calls views.onupdate which calls processmanager.onupdate
                #                                          which calls screen elements render ( screen elements are the various popups, board gui, etc and are rendered on top of each other)
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
