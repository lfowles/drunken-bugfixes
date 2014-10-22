#!/usr/bin/env python2.7
import sys
HOST, PORT = "localhost", 11982

from freecell.server.competitionserver import CompetitionServer

if __name__ == "__main__":
    debug = False
    if len(sys.argv) > 1:
        if "debug" in sys.argv:
            sys.argv.remove("debug")
            debug = True
        from pydevd import pydevd
        from debug import DEBUG_HOST, DEBUG_PORT
        pydevd.settrace(DEBUG_HOST, port=DEBUG_PORT, suspend=False)
    competition_server = CompetitionServer(HOST, PORT)
    competition_server.start()
