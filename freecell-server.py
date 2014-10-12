
HOST, PORT = "localhost", 11982

import asyncore
import asynchat
import Queue
import random
import socket
import string

from collections import namedtuple

JoinEvent = namedtuple('JoinEvent', ['id', 'version'])
QuitEvent = namedtuple('QuitEvent', ['id'])

class CompetitionServer(object):
    def __init__(self, event_queue):
        self.event_queue = event_queue
        self.competitors = {}

    def update(self):
        try:
            event = self.event_queue.get_nowait()
            self.handle_event(event)
        except Queue.Empty:
            pass

    def handle_event(self, event):
        if isinstance(event, JoinEvent):
            print "JOIN: %s v%.2f" % (event.id, event.version)

        elif isinstance(event, QuitEvent):
            print "QUIT: %s" % event.id

    def competitor_quit(self, addr):
        pass

class FreecellCompetitor(asynchat.async_chat):
    def __init__(self, sock, addr, event_queue):
        """
        :param socket.socket sock: Socket
        :param (str, int) addr: Address
        :param Queue event_queue: Event queue
        """
        asynchat.async_chat.__init__(self, sock=sock)
        self.set_terminator("\r\n")
        self.addr = addr
        self.event_queue = event_queue
        self.id = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(8))
        self.buffer = []
        self.state = "connecting"

    def handle_close(self):
        if self.state != "disconnected":
            self.event_queue.put(QuitEvent(id=self.id))
            self.state = "disconnected"

    def collect_incoming_data(self, data):
        self.buffer.append(data)

    def found_terminator(self):
        self.create_event("".join(self.buffer))
        self.buffer = []

    def create_event(self, data):
        event_type, trash, rest = data.partition(" ")
        print event_type
        if event_type == "connect":
            self.event_queue.put(JoinEvent(id=self.id, version=float(rest)))
            self.state = "connected"

class FreecellServer(asyncore.dispatcher):
    def __init__(self, host, port, event_queue):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((host, port))
        self.listen(1)
        self.event_queue = event_queue

    def handle_accept(self):
        pair = self.accept()
        if pair is not None:
            sock, addr = pair
            handler = FreecellCompetitor(sock, addr, self.event_queue)

if __name__ == "__main__":
    event_queue = Queue.Queue()
    network_server = FreecellServer(HOST, PORT, event_queue)
    competition_server = CompetitionServer(event_queue)
    while True:
        asyncore.loop(count=1, timeout=.1)
        # todo: slap that in a thread
        competition_server.update()

