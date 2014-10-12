#adapted from freecell.c http://www.linusakesson.net/software/

import copy
import curses
import random
import sys
import Queue
import time

from collections import namedtuple

ColumnSelection = namedtuple('ColumnSelection', ['col','num'])
CellSelection = namedtuple('CellSelection', ['cell'])
#Seed = namedtuple('Seed', ['seed', 'timestamp', 'next'])
#Move = namedtuple('Move', ['dest', 'auto', 'timestamp', 'previous', 'next'])
#Undo = namedtuple('Undo', ['timestamp', 'previous'])
#Selection = namedtuple('Selection', ['source', 'range', 'auto', 'timestamp', 'previous', 'next'])

InputEvent = namedtuple('InputEvent', ['key'])
MoveEvent = namedtuple('MoveEvent', ['source', 'dest', 'num'])
MoveCompleteEvent = namedtuple('MoveCompleteEvent', ['unused'])
QuitEvent = namedtuple('QuitEvent', ['won'])
MessageEvent = namedtuple('MessageEvent', ['level', 'message'])

State = namedtuple('State', ['foundations', 'cells', 'columns'])

Stats = namedtuple('Stats', ['seed', 'time', 'moves', 'undos', 'won'])

class InvalidMove(Exception):
    pass

ace_is_A = False
suites = {"c":"c", "d":"d", "h":"h", "s":"s"}

class Card(object):
    def __init__(self, value, suite):
        """
        :param int value: Value
        :param str suite: Suite
        """
        self.value = value
        self.suite = suite
        self.color = ["b", "r"][suite in ["d", "h"]]
        self.representation = None
        """:type: str | None"""

    # Can stack card onto self?
    def can_stack(self, card):
        """
        :param Card card:
        :rtype: bool
        """
        return (self.color != card.color) and (self.value == card.value + 1)

    def __str__(self):
        if self.representation is None:
            if ace_is_A and self.value == 1:
                self.representation = "A%s" % suites[self.suite]
            else:
                self.representation = "%2d%s" % (self.value, self.suite)
        return self.representation

class Deck(object):
    def __init__(self):
        self.cards = []
        """:type: list[Card]"""

    def shuffle(self, seed):
        suites = ["c", "d", "h", "s"]
        deck_nums = range(52)

        for card in range(52):
            cardsleft = 52-card
            seed = (seed * 214013 + 2531011) & 0xffffffff
            c = ((seed >> 16) & 0x7fff) % cardsleft

            value = deck_nums[c]/4+1 # Map val into 1-13 range
            suite = suites[deck_nums[c] % 4] # Map suite into Clubs, Diamonds, Hearts, Spades

            self.cards.append(Card(value, suite))

            # The following is clever...
            # Replace current card with the last card (which is no longer accessible)
            # If this _IS_ the last card, doesn't matter, because it won't be accessible in the next iteration
            deck_nums[c] = deck_nums[cardsleft-1]

        # Reverse for a natural deal
        self.cards.reverse()

    def deal(self):
        return self.cards.pop()

class Tableau(object):
    def setup(self, deck):
        self.columns = [[], [], [], [], [], [], [], []]
        """:type: list[list[Card]]"""
        self.free_cells = [None, None, None, None]
        """:type: list[Card | None]"""
        self.foundations = {"c":[], "d": [], "h": [], "s": []}
        """:type: dict[str, list[Card]]"""

        for i in range(52):
            self.columns[i%8].append(deck.deal())

    @property
    def state(self):
        state = State(foundations=copy.deepcopy(self.foundations),
                  cells = list(self.free_cells),
                  columns = copy.deepcopy(self.columns))
        return state

    @state.setter
    def state(self, state):
        self.foundations = state.foundations
        self.free_cells = state.cells
        self.columns = state.columns

    def get_card(self, source):
        """
        :param str source:
        :rtype: Card|None
        """
        source_type, index = source[0], source[1:]

        if source_type == "C":
            column = self.columns[int(index)]
            if len(column) == 0:
                return None
            else:
                return column[-1]
        elif source_type == "T":
            return self.free_cells[int(index)]
        elif source_type == "F":
            foundation = self.foundations[index]
            if len(foundation) == 0:
                return None
            else:
                return foundation[-1]

    def move(self, source, dest):
        source_type, source_index = source[0], source[1:]
        assert source_type in ("C", "T")
        dest_type, dest_index = dest[0], dest[1:]
        assert dest_type in ("C", "T", "F")

        card = self.get_card(source)
        assert card is not None

        if source_type == "C":
            self.columns[int(source_index)].pop()
        elif source_type == "T":
            self.free_cells[int(source_index)] = None

        if dest_type == "C":
            self.columns[int(dest_index)].append(card)
        elif dest_type == "T":
            self.free_cells[int(dest_index)] = card
        elif dest_type == "F":
            self.foundations[dest_index].append(card)

    def __str__(self):
        ret_str = ""
        row = []
        for i in range(52):
            if i % 8 == 0 and i > 1:
                ret_str += " ".join(row)
                ret_str += "\n"
                row = []
            row.append(str(self.columns[i%8][i/8]))

        ret_str += " ".join(row)
        return ret_str

    def height(self):
        return max([len(x) for x in self.columns])

class FreeCellLogic(object):
    def __init__(self, event_queue):
        """
        :param Queue.Queue event_queue: Event Queue
        """
        self.deck = Deck()
        self.table = Tableau()
        self.event_queue = event_queue

    def load_seed(self, seed):
        self.seed = seed
        self.deck.shuffle(seed)
        self.table.setup(self.deck)

        self.start = time.time()

        self.history = []
        self.solved = False
        self.moves = 0
        self.undos = 0
        self.move_queue = []

        self.automove()

    def handle_event(self, event):

        if isinstance(event, MoveEvent):
            self.push_undo()
            success = self.process_move(event)
            if not success:
                self.pop_undo()

        if isinstance(event, MoveCompleteEvent):
            self.automove()

        if self.is_solved():
            self.solved = True
            self.event_queue.put(QuitEvent(won=True))

    def test_supermove(self):
        foundations = {"h":[], "s":[], "c":[], "d":[]}
        columns = [[], [Card(2,"d")], [Card(2,"d")], [Card(2,"d")], [], [], [], [Card(7,"d")]]
        free_cells = [Card(13, "d"), Card(13, "d"), None, None]
        columns[0] = [Card(13,"h"), Card(12,"s"), Card(11,"h"), Card(10,"s"),
                                 Card(9,"h"), Card(8,"s"), Card(7, "h"), Card(6,"s"),
                                 Card(5,"h"), Card(4,"s"), Card(3,"h"), Card(2,"s")]

        state = State(foundations=foundations, columns=columns, cells=free_cells)
        self.table.state = state

    def can_automove(self, card):
        foundations = self.table.foundations
        if len(foundations[card.suite]) == 0:
            if card.value != 1:
                return False
            else:
                return True

        if not foundations[card.suite][-1].value == card.value - 1:
            return False

        red = ["h","d"]
        black = ["c","s"]

        if card.suite in red:
            this = red
            other = black
        else:
            this = black
            other = red

        this.remove(card.suite)

        ov1 = len(foundations[other[0]]) > 0 and foundations[other[0]][-1].value
        ov2 = len(foundations[other[1]]) > 0 and foundations[other[1]][-1].value
        sv = len(foundations[this[0]]) > 0 and foundations[this[0]][-1].value

        # Nothing to put this card on
        if ov1 >= card.value - 1 and ov2 >= card.value - 1:
            return True

        # Not sure
        if ov1 >= card.value - 2 and ov2 >= card.value - 2 \
            and sv >= card.value - 3:
            return True

    def automove(self):
        found_moves = False
        for cellno, card in enumerate(self.table.free_cells):
            if card is not None and self.can_automove(card):
                found_moves = True
                self.event_queue.put(MoveEvent(source="T%d" % cellno, dest="F%s" % card.suite, num=1))

        for colno, column in enumerate(self.table.columns):
            if len(column) > 0 and self.can_automove(column[-1]):
                found_moves = True
                self.event_queue.put(MoveEvent(source="C%d" % colno, dest="F%s" % column[-1].suite, num=1))

        if found_moves:
            self.event_queue.put(MoveCompleteEvent(unused=''))

    def is_solved(self):
        for foundation in self.table.foundations.values():
            if len(foundation) == 0 or foundation[-1].value != 13:
                return False
        return True

    def push_undo(self):
        self.history.append(self.table.state)

    def pop_undo(self):
        if len(self.history) > 0:
            self.table.state = self.history.pop()

    def fill_cells(self, move_event):
        length = move_event.num
        available_cells = ["T%d" % cell for cell, x in enumerate(self.table.free_cells) if x is None]

        if length > len(available_cells):
            return False

        for i in range(length):
            cell = available_cells[i]
            self.event_queue.put(MoveEvent(source=move_event.source, dest=cell, num=1))
        self.event_queue.put(MoveCompleteEvent(unused=''))
        return True

    def make_supermove(self, event):
        simple_state = {"free_cells": copy.deepcopy(self.table.free_cells),
                        "columns": copy.deepcopy(self.table.columns)}

        max_simple_move = len([x for x in simple_state["free_cells"] if x is None]) + 1
        stack = self.table.columns[int(event.source[1:])][-event.num:]

        available_cols = len([x for x in self.table.columns if len(x) == 0]) # this is a lower bound
        # if you write an exploratory algorithm, you'll be able to use columns that can fit SOME part of your stack

        if len(self.table.columns[int(event.dest[1:])]) == 0:
            available_cols -= 1

        source_card = stack[0]
        dest_col = simple_state["columns"][int(event.dest[1:])]
        if len(dest_col) > 0 and not dest_col[-1].can_stack(source_card):
            return False

        if len(stack) > max_simple_move * (1 + available_cols):
            return False

        #if len(stack) > max_simple_move * 2**available_cols:
        #    return False

        try:
            self.move_queue = []
            self.supermove(simple_state, stack, int(event.source[1:]), int(event.dest[1:]))
            for move in self.move_queue:
                self.event_queue.put(move)
            self.event_queue.put(MoveCompleteEvent(unused=''))
        except Exception as e:
            self.event_queue.put(MessageEvent(level="error", message=str(e)))

    def simple_supermove(self, state, stack, source, dest):
        state = copy.deepcopy(state)

        used_cells = []
        length = len(stack)
        free_cells = [cell for cell, x in enumerate(state["free_cells"]) if x is None]
        for i in range(length-1):
            cell = free_cells.pop()
            used_cells.append(cell)
            self.move_queue.append(MoveEvent(source="C%d" % source, dest="T%d" % cell, num=1))
        self.move_queue.append(MoveEvent(source="C%d" % source, dest="C%d" % dest, num=1))
        # Reverse
        for cell in reversed(used_cells):
            self.move_queue.append(MoveEvent(source="T%d" % cell, dest="C%d" % dest, num=1))

        state["columns"][dest].extend(state["columns"][source][-len(stack):])
        state["columns"][source] = state["columns"][source][:-len(stack)]

        return state

    def supermove(self, state, stack, source, dest):
        state = copy.deepcopy(state)
        max_simple_move = len([x for x in state["free_cells"] if x is None]) + 1

        remaining = len(stack) % max_simple_move
        if remaining == 0:
            remaining = max_simple_move
        # Clear top of stack
        if len(stack) > max_simple_move:
            for colno, column in enumerate(state["columns"]):
                if (len(column) == 0 or column[-1].can_stack(stack[remaining]) ) and colno != dest:
                    free_col = colno
                    break
            else:
                raise Exception("Failed to generate supermove. This is a bug.")
            state = self.supermove(state, stack[remaining:], source, free_col)

        # Move base of stack (base case!)
        state = self.simple_supermove(state, stack[:remaining], source, dest)

        # Put top of stack back onto base
        if len(stack) > max_simple_move:
            state = self.supermove(state, stack[remaining:], free_col, dest)

        return state

    def process_move(self, move_event):
        """
        :param MoveEvent move_event: Move Event
        :rtype: bool
        """
        if move_event.dest == "T":
            return self.fill_cells(move_event)

        if move_event.num > 1:
            # Really, all of these moves should be handled outside.
            # Maybe have the GUI call a movebot to generate this given the state.
            if move_event.dest.startswith("C"):
                return self.make_supermove(move_event)
            else:
                # Not going to allow moving a stack to the foundation. It might not even be possible?
                # Doesn't make sense to try and move a stack to a singular free cell either.
                return False

        card = self.table.get_card(move_event.source)

        if card is None: # Can't move a nothing
            return False

        valid = False
        dest_card = self.table.get_card(move_event.dest)

        if move_event.dest.startswith("C"):
            if dest_card is None or dest_card.can_stack(card):
                valid = True
        elif move_event.dest.startswith("T"):
            if dest_card is None:
                valid = True
        else: # foundation move uses different validation
            if dest_card is None:
                if card.value == 1:
                    valid = True
            else:
                if dest_card.value == card.value - 1:
                    valid = True

        if valid:
            self.table.move(move_event.source, move_event.dest)
            time.sleep(.1)
        return valid

    def contiguous_range(self, column):
        chain_size = 0
        lower_card = None

        # verify range is valid, otherwise use largest stack size
        for card in list(reversed(self.table.columns[column])):
            if lower_card is not None:
                if not card.can_stack(lower_card):
                    break
            lower_card = card
            chain_size += 1

        return chain_size

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

    def display_message(self, event):
        for i in range(10): # 5 seconds
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
            self.event_queue.put(QuitEvent(won=False))

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

class FreeCellGame(object):
    def __init__(self, event_queue, logic, gui, seed, debug):
        """
        :param Queue.Queue event_queue: Event Queue
        :param FreeCellLogic logic: Logic
        :param FreeCellGUI gui: GUI
        :param int seed: Seed
        """
        self.running = True
        self.event_queue = event_queue
        self.logic = logic
        self.gui = gui
        self.seed = seed
        self.stats = None
        self.debug = debug

    def start(self, stdscr):
        self.logic.load_seed(self.seed)
        self.gui.start(stdscr)
        self.game_loop()

    def game_loop(self):
        if debug:
            from pydevd import pydevd
            pydevd.settrace(DEBUG_HOST, port=DEBUG_PORT, suspend=False)

        self.gui.render()
        while self.running:
            try:
                self.gui.get_input()
                self.process_event()
            except KeyboardInterrupt:
                while not self.event_queue.empty():
                    self.event_queue.get()
                self.event_queue.put(QuitEvent(won=False))
                self.process_event()

        self.stats = Stats(seed=self.seed, time=time.time()-self.logic.start, moves=self.logic.moves, undos=self.logic.undos, won=self.logic.is_solved())

    def process_event(self):
        while not self.event_queue.empty():
            event = self.event_queue.get_nowait()

            if isinstance(event, (InputEvent, MessageEvent)):
                self.gui.handle_event(event)
            elif isinstance(event, (MoveEvent, MoveCompleteEvent)):
                self.logic.handle_event(event) # .05s sleep before move UNLESS triggered by user (immediate=True, or something like that)
            elif isinstance(event, QuitEvent):
                self.quit(event)

            self.gui.render()

    def quit(self, event):
        self.running = False


if __name__ == "__main__":

    debug = False
    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        try:
            from debug import *
            debug = True
            sys.argv.pop(1)
        except ImportError:
            pass

    event_queue = Queue.Queue()
    logic = FreeCellLogic(event_queue)
    gui = FreeCellGUI(event_queue, logic)
    if len(sys.argv) > 1:
        seed = int(sys.argv[1])
    else:
        seed = random.randint(0, 0xffffffff)
    game = FreeCellGame(event_queue, logic, gui, seed, debug)
    curses.wrapper(game.start)
    if game.stats:
        m, s = divmod(game.stats.time, 60)
        h, m = divmod(m, 60)
        time_str = "%dh%02dm%.2fs" % (h, m, s)
        if game.stats.won:
            print "You win!"
        else:
            print "Better luck next time."
        print "Seed %d, %s, %d moves, %d undos" % (game.stats.seed, time_str, game.stats.moves, game.stats.undos)