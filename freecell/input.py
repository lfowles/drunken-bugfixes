import curses

from events import InputEvent

class CursesInput(object):
    def __init__(self, event_queue):
        self.event_queue = event_queue

    def start(self, window):
        self.window = window
        curses.halfdelay(2)

    def get_input(self):
        key = self.window.getch()
        if key != curses.ERR:
            self.event_queue.put(InputEvent(key=key))
