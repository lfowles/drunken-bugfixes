import curses
import hashlib
import os.path

from events import *
import events
from input import CursesInput
from ..shared.version import VERSION

ColumnSelection = namedtuple('ColumnSelection', ['col','num'])
CellSelection = namedtuple('CellSelection', ['cell'])

class FreeCellGUI(object):
    def __init__(self, logic):
        """
        :param FreeCellLogic logic: Logic
        """
        self.logic = logic
        self.event_dispatch = events.event_dispatch

        self.screens = {}
        self.screen = "load"
        self.lock = threading.Lock()
        self.input = CursesInput(self.lock)

        self.event_dispatch.register(self.set_screen_event, ["ScreenChangeEvent"])

    def get_input(self):
        return self.input

    def start(self, stdscr):
        with self.lock:
            self.stdscr = stdscr
            self.screens["load"] = LoadGUI(self.stdscr)
            self.screens["game"] = GameGUI(self.stdscr, self.logic)
            self.screens["help"] = HelpGUI(self.stdscr)
            self.screens["login"] = LoginGUI(self.stdscr)

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

    def set_screen_event(self, event):
        self.set_screen(event.screen)

    def set_screen(self, screen):
        with self.lock:
            self.screens[self.screen].unload()
            self.screen = screen
            self.screens[self.screen].load()

    def render(self):
        with self.lock:
            self.screens[self.screen].render()

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

class LoginGUI(GUIState):
    username = ""
    token = ""
    message = ("", 0)
    def load(self):
        self.event_dispatch.register(self.handle_input, ["InputEvent"])

    def unload(self):
        self.event_dispatch.unregister(self.handle_input, ["InputEvent"])
        self.event_dispatch.unregister(self.login_reply, ["NonceEvent", "UnknownUserEvent"])
        self.event_dispatch.unregister(self.register_reply, ["NameTakenEvent", "LoginTokenEvent"])
        self.event_dispatch.unregister(self.challenge_response, ["LoggedInEvent", "LoginFailedEvent"])

    def render(self):
        self.window.erase()
        self.window.addstr(0, 0, "Login: ")
        self.window.addstr(self.username)
        if time.time() - self.message[1] < 1.0:
            self.window.addstr(1, 0, self.message[0])
        self.window.refresh()

    def handle_input(self, event):
        key = event.key
        if ord('a') <= key <= ord('z') \
            or ord('A') <= key <= ord('Z') \
            or ord('0') <= key <= ord('9') \
            or key in [ord(x) for x in "-_"]:
            self.username += chr(key)
        elif key == curses.KEY_BACKSPACE:
            self.username = self.username[:-1]
        elif key in (10, 13, curses.KEY_ENTER):
            self.event_dispatch.unregister(self.handle_input, ["InputEvent"])
            if os.path.isfile(os.path.expanduser("~/.freecell_token")):
                with open(os.path.expanduser("~/.freecell_token")) as token_file:
                    self.token = token_file.read(16)
                    self.event_dispatch.register(self.login_reply, ["NonceEvent", "UnknownUserEvent"])
                    self.event_dispatch.send(LoginEvent(username=self.username))
            else:
                self.event_dispatch.unregister(self.handle_input, ["InputEvent"])
                self.event_dispatch.register(self.register_reply, ["NameTakenEvent", "LoginTokenEvent"])
                self.event_dispatch.send(RegisterEvent(username=self.username))

    def register_reply(self, event):
        self.event_dispatch.unregister(self.register_reply, ["NameTakenEvent", "LoginTokenEvent"])
        if isinstance(event, NameTakenEvent):
            self.event_dispatch.register(self.handle_input, ["InputEvent"])
            self.message = ("Name '%s' is already taken" % self.username, time.time())
            self.username = ""
        elif isinstance(event, LoginTokenEvent):
            self.token = event.token
            self.event_dispatch.register(self.login_reply, ["NonceEvent", "UnknownUserEvent"])
            with open(os.path.expanduser("~/.freecell_token"), "w") as token_file:
                token_file.write(self.token)
            self.event_dispatch.send(LoginEvent(username=self.username))
            self.message = ("Registered '%s' successfully" % self.username, time.time())

    def login_reply(self, event):
        self.event_dispatch.unregister(self.login_reply, ["NonceEvent", "UnknownUserEvent"])
        if isinstance(event, UnknownUserEvent):
            self.event_dispatch.register(self.handle_input, ["InputEvent"])
            self.message = ("Unknown user '%s'" % self.username, time.time())
            self.username = ""
        elif isinstance(event, NonceEvent):
            self.event_dispatch.register(self.challenge_response, ["LoggedInEvent", "LoginFailedEvent"])
            nonce_hash = hashlib.sha256(hashlib.sha256(self.token+event.salt).hexdigest()+str(event.nonce)).hexdigest()
            self.event_dispatch.send(TokenHashEvent(self.username, nonce_hash))
            self.message = ("Nonce received, sending back hash", time.time())

    def challenge_response(self, event):
        self.event_dispatch.unregister(self.challenge_response, ["LoggedInEvent", "LoginFailedEvent"])
        if isinstance(event, LoggedInEvent):
            self.event_dispatch.send(ScreenChangeEvent(screen="load"))
            self.message = ("Logged in with '%s'" % self.username, time.time())
        elif isinstance(event, LoginFailedEvent):
            self.event_dispatch.register(self.handle_input, ["InputEvent"])
            self.message = ("Login failed with '%s'" % self.username, time.time())
            self.username = ""


class LoadGUI(GUIState):

    def load(self):
        self.event_dispatch.send(SeedRequestEvent())

        self.window.erase()
        self.window.addstr(0, 0, "Welcome to FREECELL")
        self.window.addstr(1, 0, "Loading seed....")
        self.window.refresh()


class HelpGUI(GUIState):
    def __init__(self, window):
        GUIState.__init__(self, window)
        self.page_num = 0


        self.help_text = [
            ("""              freecell  help              \n"""
             """                                          \n"""
             """                game rules                \n"""
             """  https://en.wikipedia.org/wiki/FreeCell  \n"""
             """                                          \n"""
             """                 feedback                 \n"""
             """      github: http://git.io/freecell      \n"""
             """   email: {bugs, features, github} -at-   \n"""
             """   knitwithlogic.com subject: freecell:   \n"""
             """v%r           p 1/4 [n]ext         e[x]it""" % VERSION),
            ("""              freecell  help              \n"""
             """                                          \n"""
             """                                          \n"""
             """                                          \n"""
             """                                          \n"""
             """                                          \n"""
             """                                          \n"""
             """                                          \n"""
             """                                          \n"""
             """v%r           p 2/4 [n]ext         e[x]it""" % VERSION)
        ]

    def load(self):
        self.event_dispatch.register(self.handle_input, ["InputEvent"])

    def unload(self):
        self.event_dispatch.unregister(self.handle_input, ["InputEvent"])
        self.page_num = 0

    def set_window(self, window):
        self.window = window

    def handle_input(self, event):
        if event.key == ord('n'):
            self.page_num += 1
        elif event.key == ord('x'):
            self.event_dispatch.send(ScreenChangeEvent(screen="game"))
            self.window.refresh()

    def render(self):

        self.window.erase()
        self.window.border('|', '|', '_', '-', ' ', ' ', '\'', '\'')

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
        self.input_buffer = []
        self.logic = logic
        self.face_dir = 1

        # for selection
        self.selected = None
        """:type : CellSelection | ColumnSelection | None"""
        self.select_num = 0
        """:type : int"""

    def load(self):
        self.event_dispatch.register(self.handle_input, ["InputEvent"])
        self.event_dispatch.register(self.pause_input, ["InputFlowEvent"])
        self.event_dispatch.register(self.display_message, ["MessageEvent"])

    def unload(self):
        self.event_dispatch.unregister(self.handle_input, ["InputEvent"])
        self.event_dispatch.unregister(self.pause_input, ["InputFlowEvent"])
        self.event_dispatch.unregister(self.display_message, ["MessageEvent"])
        self.event_dispatch.unregister(self.buffer_input, ["InputEvent"])

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

    def pause_input(self, event):
        if not event.pause:
            self.flush_input_buffer()
            self.event_dispatch.unregister(self.buffer_input, ["InputEvent"])
            self.event_dispatch.register(self.handle_input, ["InputEvent"])
        else:
            self.event_dispatch.unregister(self.handle_input, ["InputEvent"])
            if event.buffer:
                self.event_dispatch.register(self.buffer_input, ["InputEvent"])

    def buffer_input(self, event):
        self.input_buffer.append(event)

    def flush_input_buffer(self):
        for event in self.input_buffer:
            self.event_dispatch.send(event, priority=2)

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
            if card is None: # Can't move nothing to the foundation or even attempt
                return
            dest = "F%s" % card.suite

        self.event_dispatch.send(InputFlowEvent(buffer=True, pause=True), priority=1)
        move = MoveEvent(source=source, dest=dest, num=num)
        self.event_dispatch.send(move)
        self.event_dispatch.send(MoveCompleteEvent(unused=""))
        self.event_dispatch.send(InputFlowEvent(buffer=True, pause=False))
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