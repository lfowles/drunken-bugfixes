import curses
import hashlib
import os.path

from events import *
import events
from input import CursesInput

# One restriction, since input is in a separate thread:
# All curses interaction _must_ be done in render(), load(), or unload()
class GUIState(object):
    def __init__(self, window):
        self.window = window
        self.event_dispatch = events.event_dispatch

    def render(self):
        pass

    def load(self):
        pass

    def unload(self):
        pass

class HelpGUI(GUIState):
    def __init__(self, window):
        GUIState.__init__(self, window)
        self.page_num = 0

        self.help_text = [
            ("""This is the first window\n"""
             """Put some text here"""),
            ("""This is the second window\n"""
             """More text goes here\n"""
             """And some more here""")
        ]

    def load(self):
        self.event_dispatch.register(self.handle_input, ["InputEvent"])

    def unload(self):
        self.event_dispatch.unregister(self.handle_input, ["InputEvent"])

    def set_window(self, window):
        self.window = window

    def handle_input(self, event):
        if event.key == ord(' '):
            self.page_num += 1

    def render(self):

        self.window.erase()
        self.window.border('|','|','-','-','/','\\','\\','/')

        self.display_page(self.page_num)
        self.window.refresh()

    def display_page(self, page_num):
        if page_num < len(self.help_text):
            pos = 1
            for line in self.help_text[page_num].split("\n"):
                self.window.addstr(pos, 1, line)
                pos += 1
        else:
            self.window.addstr(1, 1, "Out of help!")
