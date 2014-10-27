import curses
import hashlib
import os.path

from views import HumanView
from ui import UIElement, Input, Label
from events import NameTakenEvent, LoginTokenEvent, UnknownUserEvent, NonceEvent, LoggedInEvent, LoginFailedEvent
from events import LoginEvent, RegisterEvent, TokenHashEvent

class LoginUI(UIElement):
    def __init__(self, window):
        super(LoginUI, self).__init__(window, (0,0))
        Label(self, (0,0), "Network Login")
        self.name_label = Label(self, (0, 1), "Username:")
        label_size = self.name_label.size()
        self.name_input = Input(self, (label_size.x+1, 1), max_length=10)
        self.name_input.focus = True
        self.message = Label(self, (0, 2), text="")

class MainMenuView(HumanView):
    def __init__(self, window):
        super(MainMenuView, self).__init__(window)
        self.login_ui = LoginUI(window)
        self.screens.append(self.login_ui)

    def unload(self):
        super(MainMenuView, self).unload()
        self.event_dispatch.unregister(self.login_reply, ["NonceEvent", "UnknownUserEvent"])
        self.event_dispatch.unregister(self.register_reply, ["NameTakenEvent", "LoginTokenEvent"])
        self.event_dispatch.unregister(self.challenge_response, ["LoggedInEvent", "LoginFailedEvent"])

    def keypress(self, event):
        handled = super(MainMenuView, self).keypress(event)
        if handled:
            return handled
        key = event.key
        if key in (10, 13, curses.KEY_ENTER):
            self.event_dispatch.unregister(self.keypress, ["InputEvent"])
            username = self.login_ui.name_input.text
            if os.path.isfile(os.path.expanduser("~/.freecell_token")):
                with open(os.path.expanduser("~/.freecell_token")) as token_file:
                    self.token = token_file.read(16)
                    self.event_dispatch.register(self.login_reply, ["NonceEvent", "UnknownUserEvent"])
                    self.event_dispatch.send(LoginEvent(username=username))
            else:
                self.event_dispatch.unregister(self.keypress, ["InputEvent"])
                self.event_dispatch.register(self.register_reply, ["NameTakenEvent", "LoginTokenEvent"])
                self.event_dispatch.send(RegisterEvent(username=username))
            return True
        return False

    def register_reply(self, event):
        self.event_dispatch.unregister(self.register_reply, ["NameTakenEvent", "LoginTokenEvent"])
        username = self.login_ui.name_input.text
        if isinstance(event, NameTakenEvent):
            self.event_dispatch.register(self.keypress, ["InputEvent"])
            self.login_ui.message.text = "Name '%s' is already taken" % username
            self.login_ui.name_input.text = ""
        elif isinstance(event, LoginTokenEvent):
            self.token = event.token
            self.event_dispatch.register(self.login_reply, ["NonceEvent", "UnknownUserEvent"])
            with open(os.path.expanduser("~/.freecell_token"), "w") as token_file:
                token_file.write(self.token)
            self.event_dispatch.send(LoginEvent(username=username))
            self.login_ui.message.text = "Registered '%s' successfully" % username

    def login_reply(self, event):
        self.event_dispatch.unregister(self.login_reply, ["NonceEvent", "UnknownUserEvent"])
        username = self.login_ui.name_input.text
        if isinstance(event, UnknownUserEvent):
            self.event_dispatch.register(self.keypress, ["InputEvent"])
            self.login_ui.message.text = "Unknown user '%s'" % username
            self.login_ui.name_input.text = ""
        elif isinstance(event, NonceEvent):
            self.event_dispatch.register(self.challenge_response, ["LoggedInEvent", "LoginFailedEvent"])
            nonce_hash = hashlib.sha256(hashlib.sha256(self.token+event.salt).hexdigest()+str(event.nonce)).hexdigest()
            self.event_dispatch.send(TokenHashEvent(username, nonce_hash))
            self.login_ui.message.text = "Nonce received, sending back hash"

    def challenge_response(self, event):
        self.event_dispatch.unregister(self.challenge_response, ["LoggedInEvent", "LoginFailedEvent"])
        username = self.login_ui.name_input.text
        if isinstance(event, LoggedInEvent):
            self.login_ui.message.text = "Logged in with '%s'" % username
        elif isinstance(event, LoginFailedEvent):
            self.event_dispatch.register(self.keypress, ["InputEvent"])
            self.login_ui.message.text = "Login failed with '%s'" % username
            self.login_ui.name_input.text = ""
