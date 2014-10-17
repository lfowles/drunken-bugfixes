import copy

from collections import namedtuple

State = namedtuple('State', ['foundations', 'cells', 'columns'])

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
