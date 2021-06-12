from functools import partial
from sqlalchemy import create_engine
from sqlalchemy.orm.exc import NoResultFound
import shutil
from pathlib import Path
import threading
from threading import RLock, Condition
from functools import partial
#import openpyxl
from .db import Invoice
import io
import csv

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
        
        return Context(None, partial(self.unreg, name))

    def unreg(self, name):
        with self.modlock:
            self.dblocks[name]['threads'].remove(threading.get_ident())
            with self.condition:
                if not self.dblocks[name]['threads']:
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

class CSVConverter:
    def __init__(self, session):
        self.q = q = session.query(Invoice).order_by(
            Invoice.year.desc(),
            Invoice.month.desc(),
            Invoice.day.desc(),
            Invoice.t.desc(),
            Invoice.id.desc()
        ).limit(1)
        self.offset = 0
        self.buffer = b''
    
    def read(self, size=-1):
        try:
            while len(self.buffer) < size or size < 0:
                stream = io.StringIO()
                writer = csv.writer(stream)
                
                row = self.q.offset(self.offset).scalar()
                if row.category:
                    cat_name = row.category.name
                else:
                    cat_name = ''
                writer.writerow([row.id, row.name, cat_name, row.date])
                
                items = sorted(row.items, key=lambda v: v.value)
                incomes = [c for c in items if c.value >= 0]
                expenses = [c for c in items if c.value < 0]
                
                for c in incomes:
                    writer.writerow([c.value, c.name, '', c.remark])
                    
                for c in expenses:
                    writer.writerow(['', c.name, -c.value, c.remark])
                
                total_income = sum([c.value for c in incomes])
                total_expense = sum([-c.value for c in expenses])
                writer.writerow([total_income, 'المجموع', total_expense, ''])
                
                self.buffer += stream.getvalue().encode('utf8')
                self.offset += 1
        except NoResultFound:
            pass
        
        out = self.buffer[:size]
        self.buffer = self.buffer[size:]
        return out
    
    def close(self):
        pass

def write_xlsx(session, xlsx_f):
    if not hasattr(xlsx_f, 'write'):
        with open(xlsx_f, 'wb') as f:
            return write_xlsx(session, f)
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'الفواتير'
        ws.sheet_view.rightToLeft = True
        
        q = session.query(Invoice).order_by(
            Invoice.year.desc(),
            Invoice.month.desc(),
            Invoice.day.desc(),
            Invoice.t.desc(),
            Invoice.id.desc()
        )
        
        for row in q:
            if row.category:
                cat_name = row.category.name
            else:
                cat_name = ''
            values = [row.id, row.name, cat_name, row.date]
            ws.append(values)
            last_row = ws.max_row
            for c in ws[last_row]:
                c.fill = openpyxl.styles.PatternFill(
                    fill_type = "solid", fgColor="ffff87")
            
            items = sorted(row.items, key=lambda v: v.value)
            incomes = [c for c in items if c.value >= 0]
            expenses = [c for c in items if c.value < 0]
            
            for c in incomes:
                values = [c.value, c.name, '', c.remark]
                ws.append(values)
                last_row = ws.max_row
                ws[last_row][0].fill = openpyxl.styles.PatternFill(
                    fill_type = "solid", fgColor="c3ffc3")
                
            for c in expenses:
                values = ['', c.name, -c.value, c.remark]
                ws.append(values)
                last_row = ws.max_row
                ws[last_row][2].fill = openpyxl.styles.PatternFill(
                    fill_type = "solid", fgColor="ffc3c3")
                
            total_income = sum([c.value for c in incomes])
            total_expense = sum([-c.value for c in expenses])
            values = [total_income, 'المجموع', total_expense, '']
            
            ws.append(values)
            last_row = ws.max_row
            for c in ws[last_row]:
                c.fill = openpyxl.styles.PatternFill(
                    fill_type = "solid", fgColor="c3c3ff")
            
        wb.save(xlsx_f)

def lock_connection(con, readable=True):
    if readable:
        con.execute('BEGIN IMMEDIATE')
    else:
        con.execute('BEGIN EXCLUSIVE')

def set_engine(handler, dbpath):
    engine = create_engine('sqlite:///{}'.format(dbpath))
    handler.session['dbengine'] = engine
    handler.session['dbname'] = dbpath.name

