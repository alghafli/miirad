from functools import partial
from sqlalchemy import create_engine
import shutil
from pathlib import Path

try:
    import netifaces
except ImportError:
    netifaces = None

def caller(*args):
    for c in args:
        c()

def partial_caller(*args):
    return partial(caller, *args)

def backup(f, new_f, readable=True):
    if type(f) is bytes:
        Path(new_f).write_bytes(f)
    elif hasattr(f, 'read'):
        Path(new_f).write_bytes(f.read())
    else:
        engine = create_engine('sqlite:///{}'.format(f))
        with engine.connect() as con:
            if readable:
                con.execute('BEGIN IMMEDIATE')
            else:
                con.execute('BEGIN EXCLUSIVE')
            shutil.copy(f, new_f)

def lock_connection(con, readable=True):
    with engine.connect() as con:
        if readable:
            con.execute('BEGIN IMMEDIATE')
        else:
            con.execute('BEGIN EXCLUSIVE')
        
