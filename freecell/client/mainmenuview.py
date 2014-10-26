import curses
from views import HumanView
from ui import UIElement, Input, Label
from events import event_dispatch, NameEnteredEvent

class MainMenuUI(UIElement):
    def __init__(self, window):
        super(MainMenuUI, self).__init__(window, (0,0))
        self.name_label = Label(self, (0,0), "Name:")
        label_size = self.name_label.size()
        self.name_input = Input(self, (label_size.x+1, 0), max_length=10)
        self.name_input.focus = True

    def keypress(self, event):
        handled = super(MainMenuUI, self).keypress(event)
        if handled:
            return handled
        key = event.key
        if key in (10, 13, curses.KEY_ENTER):
            event_dispatch.unregister(self.keypress, ["InputEvent"])
            event_dispatch.send(NameEnteredEvent(name=self.name_input.text))
            return True

        return False

class MainMenuView(HumanView):
    def __init__(self, window):
        super(MainMenuView, self).__init__(window)
        self.screens.append(MainMenuUI(window))

    def update(self, elapsed):
        super(MainMenuView, self).update(elapsed)

    def render(self, elapsed):
        return super(MainMenuView, self).render(elapsed)


    def unload(self):
        event_dispatch.unregister(self.keypress, ["InputEvent"])
