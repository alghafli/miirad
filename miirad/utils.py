from functools import partial
from sqlalchemy import create_engine
import shutil

try:
    import netifaces
except ImportError:
    netifaces = None

def caller(*args):
    for c in args:
        c()

def partial_caller(*args):
    return partial(caller, *args)

def backup(f, new_f):
    engine = create_engine('sqlite:///{}'.format(f))
    with engine.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        shutil.copy(f, new_f)

