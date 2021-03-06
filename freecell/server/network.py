import asynchat
import asyncore
import json
import random
import socket
import string
import threading
import time
import traceback

import events

class FreecellConnection(asynchat.async_chat):
    def __init__(self, sock, addr, lock):
        """
        :param socket.socket sock: Socket
        :param (str, int) addr: Address
        :param threading.lock lock: Network lock
        """
        asynchat.async_chat.__init__(self, sock=sock)
        self.set_terminator("\r\n")
        self.addr = addr
        self.event_dispatch = events.event_dispatch
        self.id = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(8))
        self.buffer = []
        self.state = "connecting"
        self.lock = lock

    def handle_connect(self):
        self.state = "connected"

    def handle_close(self):
        if self.state != "disconnected":
            self.event_dispatch.send(events.make_event('QuitEvent', id=self.id, reason="Client disconnected"))
            self.state = "disconnected"

    def handle_error(self):
        traceback.print_exc()

        if self.state != "disconnected":
            self.event_dispatch.send(events.make_event('QuitEvent', id=self.id, reason="Exception occurred"))
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
        print message
        if message["event"] == "connect":
            self.event_dispatch.send(events.make_event('JoinEvent', id=self.id, version=message["version"], object=self))
        elif message["event"] == "stats":
            self.event_dispatch.send(events.make_event('WinEvent', id=self.id, seed=message["seed"], time=message["time"], moves=message["moves"], undos=message["undos"], won=message["won"]))
        elif message["event"] == "tokenhash":
            self.event_dispatch.send(events.make_event('TokenHashEvent', id=self.id, username=message["username"], nonce_hash=message["nonce_hash"]))
        elif message["event"] == "login":
            self.event_dispatch.send(events.make_event('LoginEvent', id=self.id, username=message["username"]))
        elif message["event"] == "register":
            self.event_dispatch.send(events.make_event('RegisterEvent', id=self.id, username=message["username"]))
        elif message["event"] == "seedrequest":
            self.event_dispatch.send(events.make_event('SeedRequestEvent', id=self.id))

    def send_json(self, obj):
        with self.lock:
            self.push(json.dumps(obj)+"\r\n")
            print ">" + json.dumps(obj)

class FreecellServer(asyncore.dispatcher):
    def __init__(self, host, port):
        """
        :param str host: Host
        :param int port: Port
        """
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((host, port))
        self.listen(1)
        self.event_dispatch = events.event_dispatch
        self.connections = {}
        """:type : dict[(str, int), FreecellConnection]"""
        self.lock = threading.Lock()

    def run(self, shutdown_event):
        shutdown_event.wait()
        while shutdown_event.is_set():
            MAX_FPS = 30
            S_PER_FRAME = 1.0/MAX_FPS
            start = time.time()
            with self.lock:
                asyncore.loop(timeout=0, count=1)
                self.update_connections()

            elapsed = time.time()-start
            if elapsed < S_PER_FRAME:
                time.sleep(S_PER_FRAME-elapsed)

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
            handler = FreecellConnection(sock, addr, self.lock)
            self.connections[addr] = handler
