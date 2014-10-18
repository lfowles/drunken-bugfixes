import curses

import events

import select
import sys

class CursesInput(object):
    def __init__(self, curses_lock):
        self.event_dispatch = events.event_dispatch
        self.lock = curses_lock

    def start(self, window):
        self.window = window
        self.window.nodelay(1)

    def run(self):
        while True:
            r, w, x = select.select([sys.stdin], [], [])
            if len(r) > 0:
                self.get_input()

    def get_input(self):
        with self.lock:
            key = self.window.getch()
        if key != curses.ERR:
            self.event_dispatch.send(events.InputEvent(key=key), priority=2)