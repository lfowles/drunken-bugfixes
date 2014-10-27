import curses
import string

from collections import namedtuple

from logic import FreeCellLogic
from events import MoveEvent
from ui import Input, UIElement, Size
from views import HumanView

ColumnSelection = namedtuple('ColumnSelection', ['col','num'])
CellSelection = namedtuple('CellSelection', ['cell'])

class TableScreen(UIElement):
    def __init__(self, parent, position, username, table, logic, proxy=False):
        super(TableScreen, self).__init__(parent, position)
        self.table = table
        self.logic = logic
        self.face_dir = 1
        self.selected = None
        """:type : CellSelection|ColumnSelection|None"""

        self.proxy = proxy

    def size(self):
        return Size(x=44, y=self.table.height()+6+1)

    def render(self, elapsed): # render underneath other elements
        # If rendering this would be larger than the window, draw Xs instead
        max_y, max_x = self.get_window().getmaxyx()
        origin_x, origin_y = self.window_position()
        x, y = self.window_position() + self.size()
        if max_y < y+1 or max_x < x+1:
            curr_y = self.window_position().y
            if max_x-origin_x > 0 and max_y-origin_y > 0:
                for line in range(min(self.size().y, max_y-origin_y)):
                    self.get_window().hline(curr_y, origin_x, 'X', min(self.size().x, max_x-origin_x))
                    #self.get_window().insnstr(curr_y, origin_x, "X"*(min(self.size().x, max_x-origin_x)), 0)
                    curr_y += 1
        else:
            self.render_base()
            self.render_cards()
        #self.window.move(5 + self.table.height(), 43)
        return super(TableScreen, self).render(elapsed)

    def render_base(self):
        x,y = self.position
        window = self.get_window()
        if not self.proxy:
            window.addstr(y, x, "space                                  enter")
            seed_str = "#%d" % self.logic.seed
            window.addstr(y, x + 22 - len(seed_str)/2, seed_str)
        window.addstr(y + 1, x, "[   ][   ][   ][   ]    [   ][   ][   ][   ]")
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
        if not self.proxy:
            window.addstr(y + 5 + height, x, "    a    b    c    d    e    f    g    h")
        statusline = "%d move%s, %d undo%s" % (self.logic.moves, ["s",""][self.logic.moves == 1],
                                        self.logic.undos, ["s", ""][self.logic.undos == 1])
        window.addstr(y + 6 + height, x + 44 - len(statusline), statusline)
        if not self.proxy:
            window.addstr(y + 6 + height, x, "Quit undo ?=help")
            window.attrset(curses.color_pair(1))
            window.addch(y + 6 + height, x, 'Q')
            window.addch(y + 6 + height, x + 5, 'u')
            window.addch(y + 6 + height, x + 10, '?')
            window.attrset(curses.A_NORMAL)

    def render_cards(self):
        x,y = self.position
        window = self.get_window()
        # Cells
        for cellno, card in enumerate(self.table.free_cells):
            if card is not None:
                selected = isinstance(self.selected, CellSelection) \
                           and self.selected.cell == cellno

                window.move(y + 1, x + 1 + 5 *cellno)
                self.render_card(card, selected)
                window.addch(y + 2, x + 2 + 5 * cellno, "wxyz"[cellno])

        suites = "hsdc"
        for foundno, suite in enumerate(suites):
            card = self.table.get_card("F%s" % suite)
            if card is not None:
                window.move(y + 1, x + 25 + 5 * foundno)
                self.render_card(card)

        # Render cards
        for colno, column in enumerate(self.table.columns):
            selected = isinstance(self.selected, ColumnSelection) \
                       and self.selected.col == colno

            if selected:
                num = self.selected.num

            if len(column) > 0 and len(column) == len(self.logic.contiguous_range(colno)):
                window.move(y + 3, x + 3 + 5 * colno)
                window.attrset(curses.color_pair(7))
                window.addstr("   ")
                window.attrset(curses.A_NORMAL)

            for cardno, card in enumerate(column):
                window.move(y + 4 + cardno, x + 3 + 5 * colno)
                will_move = self.logic.can_automove(card)
                self.render_card(card, selected and cardno >= (len(column) - num), will_move)

    def render_card(self, card, selected=False, will_move=False):
        x,y = self.position
        window = self.get_window()
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

        window.attrset(color_pair)
        if will_move:
            window.attron(curses.A_BOLD)
        window.addstr(str(card))
        window.attrset(curses.A_NORMAL)

# Should the board be a Screen ? Or keep it as a View. hm.

class FreecellGameView(HumanView):
    def __init__(self, window, username, table, logic):
        super(FreecellGameView, self).__init__(window=window)
        self.logic = logic
        self.username = username

        self.max_tables = 3
        self.table_screen = TableScreen(window, (0,0), username, table, logic)
        self.table_screens = {username: self.table_screen}
        self.table_order = [username]

        self.num_input = Input(self.table_screen, (21, 1), max_length=2, validator=lambda key: chr(key) in string.digits)
        self.num_input.focus = True

        self.screens.append(self.table_screen)

    def add_table(self, event):
        username = event.username
        seed = event.seed
        if len(self.table_screens) < self.max_tables and username not in self.table_screens:
            num = len(self.table_order)
            self.table_order.append(username)
            logic = FreeCellLogic()
            logic.load_seed(seed)
            self.table_screens[username] = TableScreen(self.window, (num * (self.table_screen.size().x+1), 0), username, logic.table, logic)

    def remove_table(self, event):
        username = event.username
        if username in self.table_screens:
            self.screens.remove(self.table_screens[username])
            del self.table_screens[username]

    def load(self):
        super(FreecellGameView, self).load()
        # For displaying messages, we could invoke a process to add a screen and pop it when this is over
        #self.event_dispatch.register(self.display_message, ["MessageEvent"])

    def unload(self):
        super(FreecellGameView, self).unload()
        #self.event_dispatch.unregister(self.display_message, ["MessageEvent"])

    # Maybe "reflow" tables depending on terminal size
    def render(self, elapsed):
        return super(FreecellGameView, self).render(elapsed)

    def update(self, elapsed):
        # Process manager called here
        pass

    def keypress(self, event):
        handled = super(FreecellGameView, self).keypress(event)
        if handled:
            return True

        key = event.key

        # a-h Columns
        if ord('a') <= key <= ord('h'):
            column = key-ord('a')
            if self.table_screen.selected is None:
                try:
                    select_num = int(self.num_input.text)
                except ValueError:
                    select_num = 0

                if select_num > 0:
                    select_num = min(select_num, len(self.logic.contiguous_range(column)))
                else:
                    select_num = 1

                if select_num > 0:
                    self.table_screen.selected = ColumnSelection(col=column, num=select_num)

            else:
                self.create_move("C%d" % column)
                self.table_screen.selected = None
            return True

        # w-z Cells
        elif ord('w') <= key <= ord('z'):
            cell = key-ord('w')
            if self.table_screen.selected is None:
                if self.logic.table.get_card("T%d" % cell) is not None:
                    self.table_screen.selected = CellSelection(cell=cell)
            else:
                self.create_move("T%d" % cell)
                self.table_screen.selected = None
            return True

        # Enter Send to foundation
        elif key in (10, 13, curses.KEY_ENTER):
            if self.table_screen.selected is not None:
                self.create_move("F")
                self.table_screen.selected = None
            return True

        # Space Send to free cell
        elif key == 32:
            if self.table_screen.selected is not None:
                self.create_move("T")
                self.table_screen.selected = None
            return True

        # u Undo
        elif key == ord('u'):
            # TODO: UndoEvent
            self.logic.pop_undo()
            self.table_screen.selected = None
            return True

        # Escape Unselect
        elif key == 27:
            self.table_screen.selected = None
            return True

        return False

    # MoveAttemptedEvent
    def create_move(self, dest):
        assert self.table_screen.selected is not None

        if isinstance(self.table_screen.selected, ColumnSelection):
            source = "C%d" % self.table_screen.selected.col
            num = self.table_screen.selected.num
        else: # CellSelection
            source = "T%d" % self.table_screen.selected.cell
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
        self.table_screen.selected = None
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