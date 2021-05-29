from functools import partial
from sqlalchemy import create_engine
import shutil
from pathlib import Path
import threading
from threading import RLock, Condition
from functools import partial

try:
    import netifaces
except ImportError:
    netifaces = None

class Context:
    def __init__(self, func0=None, func1=None):
        self.func0 = func0
        self.func1 = func1
    
    def __enter__(self):
        if self.func0 is not None:
            self.func0()
    
    def __exit__(self, exc_type, exc_value, traceback):
        if self.func1 is not None:
            self.func1()

class DBLocker:
    def __init__(self):
        self.modlock = RLock()
        self.dblocks = {}
        self.condition = Condition()
    
    def reg(self, name):
        self.add_locker(name)
        
        locker = self.dblocks[name]
        with locker['lock']:
            with self.modlock:
                locker['threads'].add(threading.get_ident())
                print('added', threading.get_ident())
        
        return Context(None, partial(self.unreg, name))

    def unreg(self, name):
        with self.modlock:
            self.dblocks[name]['threads'].remove(threading.get_ident())
            print('removed', threading.get_ident())
            with self.condition:
                if not self.dblocks[name]['threads']:
                    print('empty')
                    self.condition.notify_all()
    
    def until_empty(self, name):
        predicate = partial(self.is_empty, name)
        with self.condition:
            self.condition.wait_for(predicate)
    
    def block_inc(self, name):
        self.add_locker(name)
        self.dblocks[name]['lock'].acquire()
        return Context(None, partial(self.unblock_inc, name))
    
    def unblock_inc(self, name):
        self.dblocks[name]['lock'].release()
    
    def add_locker(self, name):
        if name not in self.dblocks:
            with self.modlock:
                self.dblocks.setdefault(
                    name, {'lock': RLock(), 'threads': set()}
                )
    
    def is_empty(self, name):
        return not self.dblocks[name]['threads']

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
            lock_connection(con, readable)
            shutil.copy(f, new_f)

def lock_connection(con, readable=True):
    if readable:
        con.execute('BEGIN IMMEDIATE')
    else:
        con.execute('BEGIN EXCLUSIVE')

def set_engine(handler, dbpath):
    engine = create_engine('sqlite:///{}'.format(dbpath))
    handler.session['dbengine'] = engine
    handler.session['dbname'] = dbpath.name

