#!/usr/bin/env python2.7
HOST, PORT = "localhost", 11982

from freecell.server.competitionserver import CompetitionServer

if __name__ == "__main__":
    competition_server = CompetitionServer(HOST, PORT)
    competition_server.start()