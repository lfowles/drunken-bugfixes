
HOST, PORT = "localhost", 11982

import asyncore
import asynchat
import json
import Queue
import random
import socket
import string
import threading
import traceback

from collections import namedtuple


JoinEvent = namedtuple('JoinEvent', ['id', 'version', 'object'])
QuitEvent = namedtuple('QuitEvent', ['id', 'reason'])
WinEvent = namedtuple('WinEvent', ['seed', 'time', 'moves', 'undos', 'won'])
SeedEvent = namedtuple('SeedEvent', ['seed'])
#LeaderboardEvent

# last until everyone finishes seed or quits
class CompetitionServer(object):
    def __init__(self, host, port):
        self.event_queue = Queue.Queue()
        self.competitors = {}
        self.run_networking = threading.Event()
        self.networking = FreecellServer(host, port, self.event_queue, self.run_networking)
        threading.Thread(target=self.networking.run).start()
        self.running = True
        self.current_seed = random.randint(1, 0xFFFFFFFF)

    def start(self):
        self.run_networking.set()
        while self.running:
            try:
                self.update()
            except KeyboardInterrupt:
                print "Keyboard Interrupt"
                self.running = False
        self.run_networking.clear()

    def update(self):
        try:
            event = self.event_queue.get_nowait()
            self.handle_event(event)
        except Queue.Empty:
            pass

    def handle_event(self, event):
        if isinstance(event, JoinEvent):
            self.competitor_join(event)

        elif isinstance(event, QuitEvent):
            self.competitor_quit(event)

        elif isinstance(event, WinEvent):
            self.competitor_win(event)

    def competitor_win(self, event):
        print "WIN: %s" % event.id

    def competitor_join(self, event):
        print "JOIN: %s v%.2f" % (event.id, event.version)
        self.competitors[event.id] = event.object
        event.object.send_json({"event":"seed", "seed":self.current_seed})

    def competitor_quit(self, event):
        print "QUIT: %s %s" % (event.id, event.reason)
        if event.id in self.competitors:
            del self.competitors[event.id]

class FreecellConnection(asynchat.async_chat):
    def __init__(self, sock, addr, event_queue, lock):
        """
        :param socket.socket sock: Socket
        :param (str, int) addr: Address
        :param Queue.Queue event_queue: Event queue
        """
        asynchat.async_chat.__init__(self, sock=sock)
        self.set_terminator("\r\n")
        self.addr = addr
        self.event_queue = event_queue
        self.id = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(8))
        self.buffer = []
        self.state = "connecting"
        self.lock = lock

    def handle_close(self):
        if self.state != "disconnected":
            self.event_queue.put(QuitEvent(id=self.id, reason="Client disconnected"))
            self.state = "disconnected"

    def handle_error(self):
        traceback.print_exc()

        if self.state != "disconnected":
            self.event_queue.put(QuitEvent(id=self.id, reason="Exception occurred"))
            self.state = "disconnected"
            self.close()

    def collect_incoming_data(self, data):
        self.buffer.append(data)

    def found_terminator(self):
        message = json.loads("".join(self.buffer))
        self.buffer = []

        if "event" in message:
            self.create_event(message)
        else:
            print "Non-event message received"

    def create_event(self, message):
        if message["event"] == "connect":
            self.event_queue.put(JoinEvent(id=self.id, version=message["version"], object=self))

            self.state = "connected"

    def send_json(self, object):
        with self.lock:
            self.push(json.dumps(object)+"\r\n")

class FreecellServer(asyncore.dispatcher):
    def __init__(self, host, port, event_queue, run_signal):
        """
        :param str host: Host
        :param int port: Port
        :param Queue.Queue event_queue: Event Queue
        :param threading.Event run_signal: Run signal
        """
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((host, port))
        self.listen(1)
        self.event_queue = event_queue
        self.connections = {}
        """:type : dict[(str, int), FreecellConnection]"""
        self.running = run_signal
        self.lock = threading.Lock()

    def run(self):
        self.running.wait()
        while self.running.is_set():
            with self.lock:
                asyncore.loop(timeout=.1, count=1)
                self.update_connections()

        for connection in self.connections.values():
            connection.close_when_done()

    def update_connections(self):
        for addr, connection in self.connections.items():
            if connection.state == "disconnected":
                del self.connections[addr]

    def handle_accept(self):
        pair = self.accept()
        if pair is not None:
            sock, addr = pair
            handler = FreecellConnection(sock, addr, self.event_queue, self.lock)
            self.connections[addr] = handler

if __name__ == "__main__":
    competition_server = CompetitionServer(HOST, PORT)
    competition_server.start()