import hashlib
import os.path
import pickle
import random
import string

import events

if os.path.isfile(os.path.expanduser("~/.freecell_logins")):
    with open(os.path.expanduser("~/.freecell_logins")) as db_file:
        USER_DATABASE = pickle.load(db_file)
else:
    USER_DATABASE = {}

def save_database():
    with open(os.path.expanduser("~/.freecell_logins"), "w") as db_file:
        pickle.dump(USER_DATABASE, db_file)

class LoginWrapper(object):
    def __init__(self, connection):
        self.connection = connection
        self.event_dispatch = events.event_dispatch
        self.nonce = random.randint(0, 0xFFFFFFFF)

        self.event_dispatch.register(self.login, ["LoginEvent"])
        self.event_dispatch.register(self.register, ["RegisterEvent"])

    # RegisterEvent(username)
    def register(self, event):
        if event.id == self.connection.id:
            if event.username in USER_DATABASE:
                self.connection.send_json({"event":"nametaken", "username":event.username})
            else:
                salt = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for x in range(16))
                token = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for x in range(16))
                USER_DATABASE[event.username] = (hashlib.sha256(token+salt).hexdigest(), salt)
                save_database()
                self.connection.send_json({"event":"logintoken", "username":event.username, "token": token})

    # LoginEvent(username)
    def login(self, event):
        if event.id == self.connection.id:
            if event.username in USER_DATABASE:
                self.connection.send_json({"event":"nonce", "nonce":self.nonce, "salt":USER_DATABASE[event.username][1]})
                self.event_dispatch.register(self.response, ["TokenHashEvent"])
            else:
                self.connection.send_json({"event":"unknownuser", "username":event.username})

    # TokenHashEvent(username, nonce_hash)
    def response(self, event):
        if event.id == self.connection.id and event.username in USER_DATABASE:
            nonce_hash = hashlib.sha256(USER_DATABASE[event.username][0]+str(self.nonce)).hexdigest()
            if nonce_hash == event.nonce_hash:
                self.connection.send_json({"event":"loggedin", "username":event.username})
                self.event_dispatch.send(events.make_event('AuthEvent', id=self.connection.id, connection=self.connection))
            else:
                self.connection.send_json({"event":"loginfailed", "username":event.username})
            self.event_dispatch.unregister(self.response, ["TokenHashEvent"])

class LoginServer(object):
    def __init__(self):
        pass