#!/usr/bin/env python2.7
#adapted from freecell.c http://www.linusakesson.net/software/

import curses
import sys

from freecell.client.game import FreeCellGame

if __name__ == "__main__":

    debug = networking = False
    if len(sys.argv) > 1:
        if "debug" in sys.argv:
            sys.argv.remove("debug")
            debug = True

    if len(sys.argv) > 1:
        if "network" in sys.argv:
            networking = True
            sys.argv.remove("network")

    seed = None
    if not networking:
        if len(sys.argv) > 1:
            seed = int(sys.argv[1])

    game = FreeCellGame(seed, debug, networking)
    curses.wrapper(game.start)

    if game.quit_message is not None:
        print game.quit_message

    if game.stats is not None:
        m, s = divmod(game.stats.time, 60)
        h, m = divmod(m, 60)
        time_str = "%dh%02dm%.2fs" % (h, m, s)
        print "Seed %d, %s, %d moves, %d undos" % (game.stats.seed, time_str, game.stats.moves, game.stats.undos)