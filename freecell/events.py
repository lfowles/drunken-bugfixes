from collections import namedtuple

InputEvent = namedtuple('InputEvent', ['key'])
MoveEvent = namedtuple('MoveEvent', ['source', 'dest', 'num'])
MoveCompleteEvent = namedtuple('MoveCompleteEvent', ['unused'])
FinishEvent = namedtuple('FinishEvent', ['won'])
QuitEvent = namedtuple('QuitEvent', ['unused'])
MessageEvent = namedtuple('MessageEvent', ['level', 'message'])
SeedEvent = namedtuple('SeedEvent', ['seed'])
Stats = namedtuple('Stats', ['seed', 'time', 'moves', 'undos', 'won'])