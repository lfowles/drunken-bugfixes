import time

from board import Tableau, Deck, Card, State
from events import *

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
                self.pop_undo(auto=True)

        if isinstance(event, MoveCompleteEvent):
            self.automove()

        if self.is_solved():
            self.solved = True
            self.event_queue.put(FinishEvent(won=True))

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
        self.moves += 1

    def pop_undo(self, auto=False):
        if len(self.history) > 0:
            self.table.state = self.history.pop()
            self.moves -= 1
            if not auto:
                self.undos += 1

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
