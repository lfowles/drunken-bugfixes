import curses

import events

class CursesInput(object):
    def __init__(self):
        self.event_dispatch = events.event_dispatch

    def start(self, window):
        self.window = window
        curses.halfdelay(1)

    def get_input(self):
        key = self.window.getch()
        if key != curses.ERR:
            self.event_dispatch.send(events.InputEvent(key=key), priority=2)