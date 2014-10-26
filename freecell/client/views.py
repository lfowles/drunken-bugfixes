#Game View - Human
# Display - GUI/Game Scenes/etc
# Audio - SFX/Music/Speech
# Input interpreter
# Process Manager
# Options
from events import event_dispatch
from process import ProcessManager

class GameView(object):
    def __init__(self):
        self.event_dispatch = event_dispatch

    # Update all screen elements
    def update(self, elapsed):
        pass

    # Draw all screen elements
    def render(self, elapsed):
        pass

class HumanView(GameView):
    def __init__(self, window):
        super(HumanView, self).__init__()
        self.window = window
        self.screens = []
        self.processes = ProcessManager()

    def load(self):
        event_dispatch.register(self.keypress, ["InputEvent"])

    def unload(self):
        event_dispatch.unregister(self.keypress, ["InputEvent"])

    def update(self, elapsed):
        super(HumanView, self).update(elapsed)
        self.processes.update(elapsed)
        # this mainly updates visual effects, nothing to do with game logic
        for screen in self.screens:
            screen.update(elapsed)

    # render will return unique windows
    # Screens are rendered on top of the view
    def render(self, elapsed):
        super(HumanView, self).render(elapsed)
        window_list = set()
        window_list.add(self.window)
        for screen in reversed(self.screens):
            screen.render(elapsed)
            window_list.add(screen.get_window())
        return window_list

    def keypress(self, event):
        for screen in self.screens:
            if screen.keypress(event):
                return True

        return False
