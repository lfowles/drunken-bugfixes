import curses
import time

from collections import namedtuple
from events import *

ColumnSelection = namedtuple('ColumnSelection', ['col','num'])
CellSelection = namedtuple('CellSelection', ['cell'])

class FreeCellGUI(object):
    def __init__(self, event_queue, logic):
        """
        :param Queue.Queue event_queue: Event Queue
        :param FreeCellLogic logic: Logic
        """
        self.logic = logic
        self.event_queue = event_queue

        # for selection
        self.selected = None
        """:type : CellSelection | ColumnSelection | None"""
        self.select_num = 0
        """:type : int"""

        self.screens = {
            "intro": self.render_intro,
            "game": self.render_game,
                        }

    def start(self, stdscr):
        self.stdscr = stdscr
        curses.curs_set(0)
        curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLUE)
        curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)

        curses.halfdelay(2)

        self.face_dir = 1

    def get_input(self):
        key = self.stdscr.getch()
        if key != curses.ERR:
            self.event_queue.put(InputEvent(key=key))

    def handle_event(self, event):
        if isinstance(event, InputEvent):
            self.handle_input(event)
        elif isinstance(event, MessageEvent):
            self.display_message(event)

    def set_screen(self, screen):
        self.screen = screen

    def display_message(self, event):
        if self.screen == "game":
            for i in range(5): # 2.5 seconds
                self.stdscr.addstr(7+self.logic.table.height(), 0, "%s: %s" % (event.level, event.message))
                self.stdscr.refresh()
                time.sleep(.4)
                self.stdscr.deleteln()
                self.stdscr.refresh()
                time.sleep(.1)

            self.stdscr.move(5 + self.logic.table.height(), 43)

    def handle_input(self, event):
        reset_num = True
        key = event.key

        # a-h Columns
        if ord('a') <= key <= ord('h'):
            column = key-ord('a')
            if self.selected is None:
                if self.select_num > 0:
                    select_num = min(self.select_num, self.logic.contiguous_range(column))
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

        # Q quit
        elif key == ord('Q'):
            self.event_queue.put(FinishEvent(won=False))

        # s Load supermove test
        elif key == ord('s'):
            self.logic.test_supermove()
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
        self.event_queue.put(move)
        self.event_queue.put(MoveCompleteEvent(unused=""))
        self.selected = None

    def render(self):
        self.screens[self.screen]()

    def render_intro(self):
        self.stdscr.erase()
        self.stdscr.addstr(0, 0, "Welcome to FREECELL")
        self.stdscr.addstr(1, 0, "Loading seed....")
        self.stdscr.refresh()

    def render_game(self):
        self.render_base()
        self.render_cards()
        self.stdscr.refresh()
        self.stdscr.move(5 + self.logic.table.height(), 43)

    def render_base(self):
        self.stdscr.erase()
        self.stdscr.addstr(0, 0, "space                                  enter")
        seed_str = "#%d" % self.logic.seed
        self.stdscr.addstr(0, 22-len(seed_str)/2, seed_str)
        self.stdscr.addstr(1, 0, "[   ][   ][   ][   ]    [   ][   ][   ][   ]")
        if self.select_num > 0:
            self.stdscr.addstr(1, 21, str(self.select_num))
        else:
            if isinstance(self.selected, ColumnSelection):
                if self.selected.col < 4:
                    self.face_dir = 0
                else:
                    self.face_dir = 1
            self.stdscr.attrset(curses.A_BOLD | curses.color_pair(4))
            self.stdscr.addstr(1, 21, ("(=", "=)")[self.face_dir])
            self.stdscr.attrset(curses.A_NORMAL)
        height = self.logic.table.height()

        self.stdscr.addstr(5 + height, 0, "    a    b    c    d    e    f    g    h")
        statusline = "%d move%s, %d undo%s" % (self.logic.moves, ["s",""][self.logic.moves == 1],
                                        self.logic.undos, ["s", ""][self.logic.undos == 1])
        self.stdscr.addstr(6 + height, 44 - len(statusline), statusline)
        self.stdscr.addstr(6 + height, 0, "Quit undo ?=help")
        self.stdscr.attrset(curses.color_pair(1))
        self.stdscr.addch(6 + height, 0, 'Q')
        self.stdscr.addch(6 + height, 5, 'u')
        self.stdscr.addch(6 + height, 10, '?')
        self.stdscr.attrset(curses.A_NORMAL)

    def render_cards(self):
        # Cells
        for cellno, card in enumerate(self.logic.table.free_cells):
            if card is not None:
                selected = isinstance(self.selected, CellSelection) \
                           and self.selected.cell == cellno

                self.stdscr.move(1, 1 + 5 *cellno)
                self.render_card(card, selected)
                self.stdscr.addch(2, 2 + 5 * cellno, "wxyz"[cellno])

        suites = "hsdc"
        for foundno, suite in enumerate(suites):
            card = self.logic.table.get_card("F%s" % suite)
            if card is not None:
                self.stdscr.move(1, 25 + 5 * foundno)
                self.render_card(card, False)

        # Render cards
        for colno, column in enumerate(self.logic.table.columns):
            selected = isinstance(self.selected, ColumnSelection) \
                       and self.selected.col == colno

            if selected:
                num = self.selected.num

            for cardno, card in enumerate(column):
                self.stdscr.move(4 + cardno, 3 + 5 * colno)
                self.render_card(card, selected and cardno >= (len(column) - num) )

    def render_card(self, card, selected):
        if selected:
            if card.color == "r":
                color_pair = curses.color_pair(3)
            else:
                color_pair = curses.color_pair(2)
        else:
            if card.color == "r":
                color_pair = curses.color_pair(1)
            else:
                color_pair = curses.A_NORMAL

        self.stdscr.attrset(color_pair)
        self.stdscr.addstr(str(card))
        self.stdscr.attrset(curses.A_NORMAL)
