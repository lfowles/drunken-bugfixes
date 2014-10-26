import curses
import string

from collections import namedtuple

class UIElement(object):
    def __init__(self, parent, position):
        """
        :param UIElement parent: Parent element
        :param Position|(int, int)|list[int] position: Position relative to parent
        :return:
        """
        self.parent = parent
        self.position = Position(x=position[0], y=position[1]) # can pass in either a tuple or a Position
        self.children = []
        """:type : list[UIElement]"""

        if isinstance(self.parent, UIElement):
            self.parent.add_child(self)

    def keypress(self, event):
        for child in self.children:
            handled = child.keypress(event)
            if handled:
                return handled
        return False

        # In derived classes, you're going to want custom keypress code AFTER the super keypress method,
        # so children get asked first

    def update(self, elapsed):
        pass

    # maybe traverse children better so that overlapping elements are consistent (BFS vs DFS?)
    def render(self, elapsed):
        for child in self.children:
            child.render(elapsed)

    def window_position(self):
        if not isinstance(self.parent, UIElement):
            return self.position
        return self.position + self.parent.window_position()

    def get_window(self):
        if not isinstance(self.parent, UIElement):
            return self.parent
        else:
            return self.parent.get_window()

    def add_child(self, child):
        self.children.append(child)

    def remove_child(self, child):
        self.children.remove(child)

    # bounding square
    def size(self):
        max_x = 0
        max_y = 0
        for child in self.children:
            size = child.size()
            max_x = max(size.x, max_x)
            max_y = max(size.y, max_y)
        return Size(x=max_x, y=max_y)

PositionTuple = namedtuple('Position', ['x','y'])
class Position(PositionTuple):
    def __add__(self, other):
        return Position(x=self.x+other.x, y=self.y+other.y)

Size = namedtuple('Size', ['x','y'])

class Label(UIElement):
    def __init__(self, parent, position, text):
        super(Label, self).__init__(parent, position)
        self.text = text

    def render(self, elapsed):
        curses_win = self.get_window()
        window_pos = self.window_position()

        curses_win.addstr(window_pos.y, window_pos.x, self.text)

        super(Label, self).render(elapsed)

    def size(self):
        return Size(x=len(self.text), y=1)

simple_validator = lambda key: chr(key) in string.ascii_letters+string.digits
class Input(UIElement):
    def __init__(self, parent, position, max_length, validator=simple_validator): # pos is relative
        super(Input, self).__init__(parent, position)

        self.max_length = max_length
        self.validator = validator

        self.text = ""
        self.focus = False

    def keypress(self, event):
        key = event.key
        if self.focus:
            if key < 256 and self.validator(key):
                if self.max_length is not None and len(self.text) < self.max_length:
                    self.text += chr(key)
                return True
            elif key == curses.KEY_BACKSPACE:
                self.text = self.text[:-1]
                return True
        return False

    def render(self, elapsed):
        curses_win = self.get_window()
        window_pos = self.window_position()

        if self.focus:
            curses_win.attrset(curses.A_BOLD)
        pad_len = self.max_length - len(self.text)

        curses_win.addstr(window_pos.y, window_pos.x, self.text + ("_"*pad_len))
        if self.focus:
            curses_win.attrset(curses.A_NORMAL)

        super(Input, self).render(elapsed) # render children after self

    def size(self):
        return Size(x=self.max_length, y=1)