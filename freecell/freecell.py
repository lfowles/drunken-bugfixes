#adapted from freecell.c http://www.linusakesson.net/software/

import curses
import sys
import Queue

from game import FreeCellGame
from logic import FreeCellLogic
from gui import FreeCellGUI


if __name__ == "__main__":

    debug = networking = False
    if len(sys.argv) > 1:
        if sys.argv[1] == "debug":
            try:
                debug = True
                sys.argv.pop(1)
            except ImportError:
                pass
        elif sys.argv[1] == "network":
            networking = True
            sys.argv.pop(1)

    seed = None
    if not networking:
        if len(sys.argv) > 1:
            seed = int(sys.argv[1])

    game = FreeCellGame(seed, debug, networking)
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