import curses
import string

from collections import namedtuple

from events import MoveEvent
from ui import Input
from views import HumanView

ColumnSelection = namedtuple('ColumnSelection', ['col','num'])
CellSelection = namedtuple('CellSelection', ['cell'])

# Should the board be a Screen ? Or keep it as a View. hm.

class FreecellGameView(HumanView):
    def __init__(self, window, table, logic):
        super(FreecellGameView, self).__init__(window=window)
        self.table = table
        self.logic = logic
        self.selected = None
        """:type : CellSelection | ColumnSelection | None"""
        self.face_dir = 1
        self.num_input = Input(window, (21, 1), max_length=2, validator=lambda key: chr(key) in string.digits)
        self.num_input.focus = True
        self.screens.append(self.num_input)

    def load(self):
        super(FreecellGameView, self).load()
        # For displaying messages, we could invoke a process to add a screen and pop it when this is over
        #self.event_dispatch.register(self.display_message, ["MessageEvent"])

    def unload(self):
        super(FreecellGameView, self).unload()
        #self.event_dispatch.unregister(self.display_message, ["MessageEvent"])

    def update(self, elapsed):
        # Process manager called here
        pass

    def keypress(self, event):
        handled = super(FreecellGameView, self).keypress(event)
        if handled:
            return True

        reset_num = True
        key = event.key

        # a-h Columns
        if ord('a') <= key <= ord('h'):
            column = key-ord('a')
            if self.selected is None:
                try:
                    select_num = int(self.num_input.text)
                except ValueError:
                    select_num = 0

                if select_num > 0:
                    select_num = min(select_num, len(self.logic.contiguous_range(column)))
                else:
                    select_num = 1

                if select_num > 0:
                    self.selected = ColumnSelection(col=column, num=select_num)
            else:
                self.create_move("C%d" % column)
                self.selected = None
            return True

        # w-z Cells
        elif ord('w') <= key <= ord('z'):
            cell = key-ord('w')
            if self.selected is None:
                if self.logic.table.get_card("T%d" % cell) is not None:
                    self.selected = CellSelection(cell=cell)
            else:
                self.create_move("T%d" % cell)
                self.selected = None
            return True

        # Enter Send to foundation
        elif key in (10, 13, curses.KEY_ENTER):
            if self.selected is not None:
                self.create_move("F")
                self.selected = None
            return True

        # Space Send to free cell
        elif key == 32:
            if self.selected is not None:
                self.create_move("T")
                self.selected = None
            return True

        # u Undo
        elif key == ord('u'):
            # TODO: UndoEvent
            self.logic.pop_undo()
            self.selected = None
            return True

        # Escape Unselect
        elif key == 27:
            self.selected = None
            return True

        return False

    def render(self, elapsed): # render underneath screens
        self.render_base()
        self.render_cards()
        self.window.move(5 + self.table.height(), 43)
        return super(FreecellGameView, self).render(elapsed)

    def render_base(self):
        self.window.addstr(0, 0, "space                                  enter")
        seed_str = "#%d" % self.logic.seed
        self.window.addstr(0, 22-len(seed_str)/2, seed_str)
        self.window.addstr(1, 0, "[   ][   ][   ][   ]    [   ][   ][   ][   ]")
        # # this was to show the face ON TOP of the select num, but it's going to be temporarily taken out
        # if isinstance(self.selected, ColumnSelection):
        #     if self.selected.col < 4:
        #         self.face_dir = 0
        #     else:
        #         self.face_dir = 1
        # self.window.attrset(curses.A_BOLD | curses.color_pair(4))
        # self.window.addstr(1, 21, ("(=", "=)")[self.face_dir])
        # self.window.attrset(curses.A_NORMAL)
        height = self.table.height()

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
        for cellno, card in enumerate(self.table.free_cells):
            if card is not None:
                selected = isinstance(self.selected, CellSelection) \
                           and self.selected.cell == cellno

                self.window.move(1, 1 + 5 *cellno)
                self.render_card(card, selected)
                self.window.addch(2, 2 + 5 * cellno, "wxyz"[cellno])

        suites = "hsdc"
        for foundno, suite in enumerate(suites):
            card = self.table.get_card("F%s" % suite)
            if card is not None:
                self.window.move(1, 25 + 5 * foundno)
                self.render_card(card)

        # Render cards
        for colno, column in enumerate(self.table.columns):
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

    def create_move(self, dest):
        assert self.selected is not None

        if isinstance(self.selected, ColumnSelection):
            source = "C%d" % self.selected.col
            num = self.selected.num
        else: # CellSelection
            source = "T%d" % self.selected.cell
            num = 1

        # TODO: patch this up in logic, not here
        if dest == "F":
            # Get suite
            card = self.logic.table.get_card(source)
            if card is None: # Can't move nothing to the foundation or even attempt
                return
            dest = "F%s" % card.suite

        move = MoveEvent(source=source, dest=dest, num=num)
        self.event_dispatch.send(move)
        self.selected = None
    #
    # def display_message(self, event):
    #     for i in range(5): # 2.5 seconds
    #         self.window.addstr(7+self.logic.table.height(), 0, "%s: %s" % (event.level, event.message))
    #         self.window.refresh()
    #         time.sleep(.4)
    #         self.window.deleteln()
    #         self.window.refresh()
    #         time.sleep(.1)
    #
    #     self.window.move(5 + self.logic.table.height(), 43)