import curses
import time

import events

from collections import namedtuple
from events import *

ColumnSelection = namedtuple('ColumnSelection', ['col','num'])
CellSelection = namedtuple('CellSelection', ['cell'])

class FreeCellGUI(object):
    def __init__(self, logic):
        """
        :param Queue.Queue event_queue: Event Queue
        :param FreeCellLogic logic: Logic
        """
        self.logic = logic
        self.event_dispatch = events.event_dispatch

        self.screens = {}
        self.screen = "intro"

    def start(self, stdscr):
        self.stdscr = stdscr
        self.screens["intro"] = LoadGUI(self.stdscr)
        self.screens["game"] = GameGUI(self.stdscr, self.logic)
        self.screens["help"] = HelpGUI(self.stdscr,)

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

    def set_screen(self, screen):
        self.screens[self.screen].unload()
        self.screen = screen
        self.screens[self.screen].load()

    def render(self):
        self.screens[self.screen].render()

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

class LoadGUI(GUIState):

    def render(self):
        self.window.erase()
        self.window.addstr(0, 0, "Welcome to FREECELL")
        self.window.addstr(1, 0, "Loading seed....")
        self.window.refresh()

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

class GameGUI(GUIState):
    def __init__(self, window, logic):
        GUIState.__init__(self, window)
        self.logic = logic
        self.face_dir = 1

        # for selection
        self.selected = None
        """:type : CellSelection | ColumnSelection | None"""
        self.select_num = 0
        """:type : int"""

    def load(self):
        self.event_dispatch.register(self.handle_input, ["InputEvent"])
        self.event_dispatch.register(self.display_message, ["MessageEvent"])

    def unload(self):
        self.event_dispatch.unregister(self.handle_input, ["InputEvent"])
        self.event_dispatch.unregister(self.display_message, ["MessageEvent"])

    def render(self):
        self.render_base()
        self.render_cards()
        self.window.refresh()
        self.window.move(5 + self.logic.table.height(), 43)

    def render_base(self):
        self.window.erase()
        self.window.addstr(0, 0, "space                                  enter")
        seed_str = "#%d" % self.logic.seed
        self.window.addstr(0, 22-len(seed_str)/2, seed_str)
        self.window.addstr(1, 0, "[   ][   ][   ][   ]    [   ][   ][   ][   ]")
        if self.select_num > 0:
            self.window.addstr(1, 21, str(self.select_num))
        else:
            if isinstance(self.selected, ColumnSelection):
                if self.selected.col < 4:
                    self.face_dir = 0
                else:
                    self.face_dir = 1
            self.window.attrset(curses.A_BOLD | curses.color_pair(4))
            self.window.addstr(1, 21, ("(=", "=)")[self.face_dir])
            self.window.attrset(curses.A_NORMAL)
        height = self.logic.table.height()

        self.window.addstr(5 + height, 0, "    a    b    c    d    e    f    g    h")
        statusline = "%d move%s, %d undo%s" % (self.logic.moves, ["s",""][self.logic.moves == 1],
                                        self.logic.undos, ["s", ""][self.logic.undos == 1])
        self.window.addstr(6 + height, 44 - len(statusline), statusline)
        self.window.addstr(6 + height, 0, "Quit undo ?=help")
        self.window.attrset(curses.color_pair(1))
        self.window.addch(6 + height, 0, 'Q')
        self.window.addch(6 + height, 5, 'u')
        self.window.addch(6 + height, 10, '?')
        self.window.attrset(curses.A_NORMAL)

    def render_cards(self):
        # Cells
        for cellno, card in enumerate(self.logic.table.free_cells):
            if card is not None:
                selected = isinstance(self.selected, CellSelection) \
                           and self.selected.cell == cellno

                self.window.move(1, 1 + 5 *cellno)
                self.render_card(card, selected)
                self.window.addch(2, 2 + 5 * cellno, "wxyz"[cellno])

        suites = "hsdc"
        for foundno, suite in enumerate(suites):
            card = self.logic.table.get_card("F%s" % suite)
            if card is not None:
                self.window.move(1, 25 + 5 * foundno)
                self.render_card(card)

        # Render cards
        for colno, column in enumerate(self.logic.table.columns):
            selected = isinstance(self.selected, ColumnSelection) \
                       and self.selected.col == colno

            if selected:
                num = self.selected.num

            if len(column) > 0 and len(column) == len(self.logic.contiguous_range(colno)):
                self.window.move(3, 3 + 5 * colno)
                self.window.attrset(curses.color_pair(7))
                self.window.addstr("   ")
                self.window.attrset(curses.A_NORMAL)

            for cardno, card in enumerate(column):
                self.window.move(4 + cardno, 3 + 5 * colno)
                will_move = self.logic.can_automove(card)
                self.render_card(card, selected and cardno >= (len(column) - num), will_move)

    def render_card(self, card, selected=False, will_move=False):
        #Precedence is selected > automove > default

        if card.color == "r":
            color_pair = curses.color_pair(1)
        else:
            color_pair = curses.A_NORMAL

        if selected:
            if card.color == "r":
                color_pair = curses.color_pair(3)
            else:
                color_pair = curses.color_pair(2)

        self.window.attrset(color_pair)
        if will_move:
            self.window.attron(curses.A_BOLD)
        self.window.addstr(str(card))
        self.window.attrset(curses.A_NORMAL)

    def handle_input(self, event):
        reset_num = True
        key = event.key

        # a-h Columns
        if ord('a') <= key <= ord('h'):
            column = key-ord('a')
            if self.selected is None:
                if self.select_num > 0:
                    select_num = min(self.select_num, len(self.logic.contiguous_range(column)))
                else:
                    select_num = 1

                if select_num > 0:
                    self.selected = ColumnSelection(col=column, num=select_num)
            else:
                self.create_move("C%d" % column)
                self.selected = None

        # w-z Cells
        elif ord('w') <= key <= ord('z'):
            cell = key-ord('w')
            if self.selected is None:
                if self.logic.table.get_card("T%d" % cell) is not None:
                    self.selected = CellSelection(cell=cell)
            else:
                self.create_move("T%d" % cell)
                self.selected = None

        # 0-9 Range modifier
        elif ord('0') <= key <= ord('9'):
            self.selected = None
            new_mod = self.select_num * 10 + int(key-ord('0'))
            if new_mod < 100:
                self.select_num = new_mod
            reset_num = False

        # Enter Send to foundation
        elif key in (10, 13, curses.KEY_ENTER):
            if self.selected is not None:
                self.create_move("F")
                self.selected = None

        # Space Send to free cell
        elif key == 32:
            if self.selected is not None:
                self.create_move("T")
                self.selected = None

        # u Undo
        elif key == ord('u'):
            self.logic.pop_undo()
            self.selected = None

        # Escape Unselect
        elif key == 27:
            self.selected = None

        if reset_num:
            self.select_num = 0

    def create_move(self, dest):
        assert self.selected is not None

        if isinstance(self.selected, ColumnSelection):
            source = "C%d" % self.selected.col
            num = self.selected.num
        else: # CellSelection
            source = "T%d" % self.selected.cell
            num = 1

        if dest == "F":
            # Get suite
            card = self.logic.table.get_card(source)
            dest = "F%s" % card.suite

        move = MoveEvent(source=source, dest=dest, num=num)
        self.event_dispatch.send(move)
        self.event_dispatch.send(MoveCompleteEvent(unused=""))
        self.selected = None

    def display_message(self, event):
        for i in range(5): # 2.5 seconds
            self.window.addstr(7+self.logic.table.height(), 0, "%s: %s" % (event.level, event.message))
            self.window.refresh()
            time.sleep(.4)
            self.window.deleteln()
            self.window.refresh()
            time.sleep(.1)

        self.window.move(5 + self.logic.table.height(), 43)