from cofan import BaseProvider, BaseHandler, Patterner
from http import cookies
import random
from pathlib import Path
from sqlalchemy import create_engine, desc, asc
from sqlalchemy.orm import Session
from .utils import partial_caller, backup, set_engine, DBLocker, write_xlsx, CSVConverter
from .db import *
from .users_db import User
import io
import http
import urllib.parse
import traceback
from cgi import parse_header
import multipart
import json
from sqlalchemy.sql.expression import literal_column
import math
from . import multicalendar
import datetime
from http import HTTPStatus
import time
import tempfile
import operator
import hashlib

def is_integer(v):
    try:
        int(v)
        return True
    except ValueError:
        return False

class PostHandler(BaseHandler):
    def do_POST(self):
        '''
        same as `BaseHandler.do_GET()` but calles `self.post_response()` instead
        of `self.get_response()`
        '''
        
        response, headers, content, postproc = self.post_response()
        try:
            self.send_response(response)
            for c in headers:
                self.send_header(c, headers[c])
            self.end_headers()
            data = content.read(1024)
            while data:
                self.wfile.write(data)
                data = content.read(1024)
        finally:
            content.close()
            postproc()
    
    def post_response(self):
        '''
        Same as `BaseProvider.get_response()` but calls
        `self.provider.post_content()` instead of `self.provider.get_content()`.
        It also does not modify headers (e.g. if there is Range request header,
        it does not respond with 204 but keep the response code and content
        without change.
        '''
        
        url = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(url.path)[1:]
        query = urllib.parse.parse_qs(url.query)
        return self.provider.post_content(self, path, query, full_url=path)
    
    def __call__(self, *args, **kwargs):
        '''
        Creates and returns another instance of the same type as `self` with
        the same provider. Any arguments and keyword arguments are passed to the
        constructor of `http.server.BaseHTTPRequestHandler`.
        '''
        
        handler = type(self)(self.provider)
        http.server.BaseHTTPRequestHandler.__init__(handler, *args, **kwargs)
        return handler

class Texter(BaseProvider):
    def __init__(self, path):
        self.path = Path(path).resolve()
    
    def get_content(self, handler, url, query={}, full_url=''):
        f = self.path.read_text('utf-8')
        
        response = http.HTTPStatus.OK
        headers = {}
        
        return response, headers, f, lambda: None

class PostPatterner(Patterner):
    'like `Patterner` but defines `post_content()` method'
    def post_content(self, handler, url, query={}, full_url=''):
        try:
            for pattern, provider in self.patterns:
                if pattern.match(url):
                    new_url = pattern.sub('', url, count=1)
                    return provider.post_content(handler, new_url, query, full_url)
            else:
                return self.short_response(http.HTTPStatus.NOT_FOUND)
        except Exception as e:
            print('exception in {}'.format(type(self).__name__))
            print(traceback.format_exc())
            return self.short_response(http.HTTPStatus.INTERNAL_SERVER_ERROR)
    
class Checker(BaseProvider):
    def __init__(self):
        self.checks = []
        self.else_ = None
    
    def check(self, handler, url, query={}, full_url=''):
        for c in self.checks:
            if c[0](handler, url, query, full_url):
                return c[1]
        else:
            return self.else_
    
    def get_content(self, handler, url, query={}, full_url=''):
        provider = self.check(handler, url, query, full_url)
        return provider.get_content(handler, url, query, full_url)

class Sessioner(Checker):
    def __init__(self, provider):
        self.sessions = {}
        self.checks = (self.check_session, provider),
        self.else_ = None
        self.current_session = random.randint(0, 0xffff)
    
    def check_session(self, handler, url, query={}, full_url=''):
        c = cookies.SimpleCookie()
        if 'Cookie' in handler.headers:
            c.load(handler.headers['Cookie'])
        
        if ('session_id' not in c or
                int(c['session_id'].value) not in self.sessions):
            self.sessions[self.current_session] = {}
            handler._session_id = self.current_session
            handler.new_session = True
            self.current_session += 1
        else:
            handler._session_id = int(c['session_id'].value)
            handler.new_session = False
        
        return True
    
    def get_content(self, handler, url, query={}, full_url=''):
        p = self.check(handler, url, query, full_url)
        
        handler.session = self.sessions[handler._session_id]
        response, headers, f, postproc = \
            p.get_content(handler, url, query, full_url)
        
        if handler.new_session:
            headers['Set-Cookie'] = 'session_id={}; SameSite=Strict'.format(handler._session_id)
        
        return response, headers, f, postproc
    
    def post_content(self, handler, url, query={}, full_url=''):
        p = self.check(handler, url, query, full_url)
        
        handler.session = self.sessions[handler._session_id]
        response, headers, f, postproc = \
            p.post_content(handler, url, query, full_url)
        
        if handler.new_session:
            headers['Set-Cookie'] = 'session_id={}'.format(handler._session_id)
        
        return response, headers, f, postproc

class DBSelector(BaseProvider):
    locker = DBLocker()
    def __init__(self, path, provider):
        self.path = Path(path).resolve()
        self.provider = provider
    
    def get_content(self, handler, url, query={}, full_url=''):
        if 'dbengine' not in handler.session:
            p = self.path / 'db'
            p.mkdir(parents=True, exist_ok=True)
            dbs = list(p.iterdir())
            if dbs:
                latest_db = max(dbs, key=lambda p: p.stat().st_atime)
                set_engine(handler, latest_db)
            else:
                f = io.BytesIO()
            
                response = http.HTTPStatus.SEE_OTHER
                length = f.seek(0, 2)
                f.seek(0)
                headers = {
                        'Content-Type':'text/plain;charset=utf-8',
                        'Content-Length': length,
                        'Location': '/edit_db'
                    }
                
                return response, headers, f, lambda: None
        
        with self.locker.reg(handler.session['dbname']):
            db_dir = self.path / 'db'
            db_path = db_dir / handler.session['dbname']
            if db_path.exists():
                handler.dbsession = Session(handler.session['dbengine'])
                
                response, headers, f, postproc = \
                    self.provider.get_content(handler, url, query, full_url)
                postproc = partial_caller(handler.dbsession.close, postproc)
                return response, headers, f, postproc
            elif list(db_dir.iterdir()):
                f = io.BytesIO()
            
                response = http.HTTPStatus.SEE_OTHER
                length = f.seek(0, 2)
                f.seek(0)
                headers = {
                        'Content-Type':'text/plain;charset=utf-8',
                        'Content-Length': length,
                        'Location': '/db_list'
                    }
                
                return response, headers, f, lambda: None
            else:
                f = io.BytesIO()
            
                response = http.HTTPStatus.SEE_OTHER
                length = f.seek(0, 2)
                f.seek(0)
                headers = {
                        'Content-Type':'text/plain;charset=utf-8',
                        'Content-Length': length,
                        'Location': '/edit_db'
                    }
                
                return response, headers, f, lambda: None
    
    def post_content(self, handler, url, query={}, full_url=''):
        if 'dbengine' not in handler.session:
            p = self.path / 'db'
            p.mkdir(parents=True, exist_ok=True)
            dbs = list(p.iterdir())
            if dbs:
                latest_db = max(dbs, key=lambda p: p.stat().st_atime)
                set_engine(handler, latest_db)
            else:
                f = io.BytesIO()
                
                response = http.HTTPStatus.SEE_OTHER
                length = f.seek(0, 2)
                f.seek(0)
                headers = {
                        'Content-Type':'text/plain;charset=utf-8',
                        'Content-Length': length,
                        'Location': '/edit_db'
                    }
                
                return response, headers, f, lambda: None
        
        with self.locker.reg(handler.session['dbname']):
            db_dir = self.path / 'db'
            db_path = db_dir / handler.session['dbname']
            if db_path.exists():
                handler.dbsession = Session(handler.session['dbengine'])
            
                response, headers, f, postproc = \
                    self.provider.post_content(handler, url, query, full_url)
                postproc = partial_caller(handler.dbsession.close, postproc)
                return response, headers, f, postproc
            elif list(db_dir.iterdir()):
                f = io.BytesIO()
            
                response = http.HTTPStatus.SEE_OTHER
                length = f.seek(0, 2)
                f.seek(0)
                headers = {
                        'Content-Type':'text/plain;charset=utf-8',
                        'Content-Length': length,
                        'Location': '/db_list'
                    }
                
                return response, headers, f, lambda: None
            else:
                f = io.BytesIO()
            
                response = http.HTTPStatus.SEE_OTHER
                length = f.seek(0, 2)
                f.seek(0)
                headers = {
                        'Content-Type':'text/plain;charset=utf-8',
                        'Content-Length': length,
                        'Location': '/edit_db'
                    }
                
                return response, headers, f, lambda: None
            

class DBEditor(BaseProvider):
    def __init__(self, path):
        self.path = Path(path).resolve()
    
    def get_content(self, handler, url, query={}, full_url=''):
        p = Path(__file__).parent / 'data/html/edit_db.html'
        f = p.read_text('utf-8')
        
        response = http.HTTPStatus.OK
        headers = {}
        
        return response, headers, f, lambda: None
    
    def post_content(self, handler, url, query={}, full_url=''):
        l = int(handler.headers['Content-Length'])
        content_type, pdict = parse_header(handler.headers['Content-Type'])
        
        content = handler.rfile.read(l)
        stream = io.BytesIO(content)
        mp = multipart.MultipartParser(
            stream, pdict['boundary'], len(content), charset='utf8')
        
        content = {}
        
        for c in mp:
            if c.name not in content:
                content[c.name] = c.value
        
        engine = self.create_db(content['dbname'])
        handler.session['dbengine'] = engine
        handler.session['dbname'] = '{}.sqlite3'.format(content['dbname'])
        try:
            session = Session(handler.session['dbengine'])
            Config.set(session, 'calendar', content['dbcalendar'])
            session.commit()
        finally:
            session.close()
        
        f = io.BytesIO()
            
        response = http.HTTPStatus.SEE_OTHER
        length = f.seek(0, 2)
        f.seek(0)
        headers = {
                'Content-Type':'text/plain;charset=utf-8',
                'Content-Length': length,
                'Location': '/'
            }
        
        return response, headers, f, lambda: None
    
    def create_db(self, dbname):
        print('create', dbname)
        dbpath = self.path / 'db' / '{}.sqlite3'.format(dbname)
        dbpath.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine('sqlite:///{}'.format(dbpath))
        Base.metadata.create_all(engine)
        
        return engine

class Templater(Checker):
    def __init__(self, path, provider):
        self.template = Path(path).read_text('utf8')
        self.provider = provider
    
    def get_content(self, handler, url, query={}, full_url=''):
        response, headers, f, postproc = \
            self.provider.get_content(handler, url, query, full_url)
        
        try:
            dbname = Path(handler.session['dbname']).stem
            db_label = '<label class="dbname-label">{}</label>'.format(dbname)
        except Exception:
            db_label = ''
        if type(f) is str:
            page = self.template.format(content=f, db_label=db_label)
            f = io.BytesIO(page.encode('utf8'))
            
            length = f.seek(0, 2)
            f.seek(0)
            headers['Content-Type'] = 'text/html;charset=utf-8'
            headers['Content-Length'] = length
        
        return response, headers, f, postproc
    
    def post_content(self, handler, url, query={}, full_url=''):
        response, headers, f, postproc = \
            self.provider.post_content(handler, url, query, full_url)
        
        if type(f) is str:
            page = self.template.format(content=f)
            f = io.BytesIO(page.encode('utf8'))
            
            length = f.seek(0, 2)
            f.seek(0)
            headers['Content-Type'] = 'text/html;charset=utf-8'
            headers['Content-Length'] = length
        
        return response, headers, f, postproc

class Indexer(BaseProvider):
    @staticmethod
    def get_content(handler, url, query={}, full_url=''):
        cal = Config.get(handler.dbsession, 'calendar', default='gregorian')
        last_month, last_day = multicalendar.date_values(cal)
        years = []
        months = []
        days = []
        
        fy = handler.dbsession.query(
                Invoice.year
            ).order_by(
                Invoice.year
            ).first()
        
        ly = handler.dbsession.query(
                Invoice.year
            ).order_by(
                Invoice.year.desc()
            ).first()
        
        if fy is not None and ly is not None:
            fy = fy[0]
            ly = ly[0]
            for c in range(fy, ly+1):
                years.append('<option>{}</option>'.format(c))
        
        for c in range(last_month):
            months.append('<option>{}</option>'.format(c+1))
        
        for c in range(last_day):
            days.append('<option>{}</option>'.format(c+1))
        
        p = Path(__file__).parent / 'data/html/index.html'
        f = p.read_text('utf-8')
        f = f.format(years='\n'.join(years), months='\n'.join(months),
            days='\n'.join(days))
        
        response = http.HTTPStatus.OK
        headers = {}
        
        return response, headers, f, lambda: None

class Categorier(BaseProvider):
    @staticmethod
    def get_content(handler, url, query={}, full_url=''):
        results = handler.dbsession.query(Category).order_by(
            Category.name).all()
        
        out = []
        for c in results:
            out.append({'id': c.id, 'name': c.name})
        
        page = json.dumps(out)
        f = io.BytesIO(page.encode('utf8'))
        
        length = f.seek(0, 2)
        f.seek(0)
        headers = {
            'Content-Type': 'application/json;charset=utf-8',
            'Content-Length': length
        }
        
        response = http.HTTPStatus.OK
        
        return response, headers, f, lambda: None

class InvoiceLister(BaseProvider):
    @staticmethod
    def get_content(handler, url, query={}, full_url=''):
        LIMIT = 10
        for c in query:
            query[c] = query[c][0]
        
        try:
            page = int(query['page'])
        except Exception:
            print(traceback.format_exc())
            page = 0
        
        invoice_date = Invoice.date.label('invoice_date')
        item_count = func.count(Invoice.items)
        income = func.sum(Item.income).label('income')
        expense = func.sum(Item.expense).label('expense')
        item_sum = income - expense
        q = handler.dbsession.query(
                Invoice.id, invoice_date, Invoice.name, Category.name,
                item_count, income, expense
            ).outerjoin(
                Invoice.category
            ).outerjoin(
                Invoice.items
            ).group_by(
                Invoice.id
            ).order_by(
                Invoice.year.desc(),
                Invoice.month.desc(),
                Invoice.day.desc(),
                Invoice.t.desc(),
                Invoice.id.desc()
            )
        
        if query.setdefault('q', ''):
            q = q.filter(Invoice.name.contains(query['q']))
        if is_integer(query.setdefault('category', '')):
            q = q.filter(Category.id == int(query['category']))
        if (
                query.setdefault('year0', '').isdigit() and
                query.setdefault('month0', '').isdigit() and
                query.setdefault('day0', '').isdigit()
        ):
            date0 = (
                int(query['year0']),
                int(query['month0']),
                int(query['day0'])
            )
            date0 = '{:04}-{:02}-{:02}'.format(*date0)
            q = q.filter(Invoice.date >= date0)
        if (
                query.setdefault('year1', '').isdigit() and
                query.setdefault('month1', '').isdigit() and
                query.setdefault('day1', '').isdigit()
        ):
            date1 = (
                int(query['year1']),
                int(query['month1']),
                int(query['day1'])
            )
            date1 = '{:04}-{:02}-{:02}'.format(*date1)
            q = q.filter(Invoice.date <= date1)
        if (
                is_integer(query.setdefault('value0', '')) and
                is_integer(query.setdefault('value1', ''))
        ):
            value0 = int(query['value0'])
            value1 = int(query['value1'])
            q = q.having(item_sum.between(value0, value1))
        elif is_integer(query['value0']):
            q = q.having(item_sum >= int(query['value0']))
        elif is_integer(query.setdefault('value1', '')):
            q = q.having(item_sum <= int(query['value1']))
        
        count = q.count()
        last_page = math.ceil(count / LIMIT) - 1
        if page < 0:
            page = 0
        elif page > last_page:
            page = last_page
        
        results = q.offset(LIMIT * page).limit(LIMIT).all()
        
        page = json.dumps(
            {'page': page, 'results': results, 'pages': last_page + 1})
        f = io.BytesIO(page.encode('utf8'))
        
        length = f.seek(0, 2)
        f.seek(0)
        headers = {
            'Content-Type': 'application/json;charset=utf-8',
            'Content-Length': length
        }
        
        response = http.HTTPStatus.OK
        
        return response, headers, f, lambda: None

class InvoiceViewer(BaseProvider):
    @staticmethod
    def get_content(handler, url, query={}, full_url=''):
        p = Path(__file__).parent / 'data/html/invoice.html'
        f = p.read_text('utf-8')
        
        try:
            id_ = int(query.setdefault('id', '')[0])
            invoice = handler.dbsession.query(Invoice).get(id_)
            if invoice is None:
                raise ValueError
            
            incomes = []
            expenses = []
            sums = []
            income_template = (
                '<tr>' +
                '<td>{0.name}</td>' +
                '<td>{1:0.2f}</td>' +
                '<td></td>' +
                '<td>{0.remark}</td>' +
                '</tr>'
            )
            expense_template = (
                '<tr>' +
                '<td>{0.name}</td>' +
                '<td></td>' +
                '<td>{1:0.2f}</td>' +
                '<td>{0.remark}</td>' +
                '</tr>'
            )
            
            for item in sorted(invoice.items, key=lambda c: abs(c.value)):
                if item.expense:
                    expenses.append(expense_template.format(item, item.expense))
                else:
                    incomes.append(income_template.format(item, item.income))
            
            if invoice.category is not None:
                category = invoice.category.name
            else:
                category = ''
            
            total_incomes = sum(
                [c.value for c in invoice.items if c.value >= 0])
            total_expenses = sum(
                [-c.value for c in invoice.items if c.value < 0])
            total = total_incomes - total_expenses
            
            income_template = (
                '<tr>' +
                '<td>{}</td>' +
                '<td>{:0.2f}</td>' +
                '<td></td>' +
                '<td></td>' +
                '</tr>'
            )
            expense_template = (
                '<tr>' +
                '<td>{}</td>' +
                '<td></td>' +
                '<td>{:0.2f}</td>' +
                '<td></td>' +
                '</tr>'
            )
            
            sums.append(
                income_template.format('?????????? ??????????????????', total_incomes))
            
            sums.append(
                expense_template.format('?????????? ????????????????', total_expenses))
            
            if total >= 0:
                grand_total_incomes = '<label class="default-input medium-input total-field">{:.2f}</label>'.format(total)
                grand_total_expenses = ''
            else:
                grand_total_incomes = ''
                grand_total_expenses = '<label class="default-input medium-input total-field">{:.2f}</label>'.format(-total)
            
            
            mod_template = (
                '<tr>' +
                '<td><label class="default-label">{}</label></td>' +
                '<td><label class="default-label">{}</label></td>' +
                '</tr>'
            )
            
            mods = []
            
            for mod in sorted(invoice.modifications, key=lambda c: c.timestamp):
                mods.append(
                  mod_template.format(
                      time.strftime('%Y-%m-%d %H:%M:%S',
                        time.localtime(mod.timestamp)
                      ),
                      mod.username
                    )
                  )
            
            incomes = '\n'.join(incomes)
            expenses = '\n'.join(expenses)
            mods = '\n'.join(mods)
            
            f = f.format(
                invoice=invoice, category=category,
                items=incomes+expenses,
                total_incomes=total_incomes,
                total_expenses=total_expenses,
                grand_total_expenses=grand_total_expenses,
                grand_total_incomes=grand_total_incomes,
                mods=mods
              )
        except ValueError:
            return BaseProvider.short_response(http.HTTPStatus.NOT_FOUND)
        
        response = http.HTTPStatus.OK
        headers = {}
        
        return response, headers, f, lambda: None

class InvoiceDeleter(BaseProvider):
    @staticmethod
    def get_content(handler, url, query={}, full_url=''):
        p = Path(__file__).parent / 'data/html/delete.html'
        f = p.read_text('utf-8')
        
        id_ = query['id'][0]
        message = '?????? ???????????????? ?????? {}??'.format(id_)
        inputs = '<input type="hidden" name="id" value="{}">'.format(id_)
        back_url = 'invoice?id={}'.format(id_)
        f = f.format(message=message, inputs=inputs, back_url=back_url)
        
        response = http.HTTPStatus.OK
        headers = {}
        
        return response, headers, f, lambda: None
    
    @staticmethod
    def post_content(handler, url, query={}, full_url=''):
        l = int(handler.headers['Content-Length'])
        content_type, pdict = parse_header(handler.headers['Content-Type'])
        
        content = handler.rfile.read(l)
        stream = io.BytesIO(content)
        mp = multipart.MultipartParser(
            stream, pdict['boundary'], len(content), charset='utf8')
        
        content = {}
        
        for c in mp:
            if c.name not in content:
                content[c.name] = c.value
        
        id_ = content['id']
        invoice = handler.dbsession.query(Invoice).get(id_)
        handler.dbsession.delete(invoice)
        handler.dbsession.commit()
        
        f = io.BytesIO()
            
        response = http.HTTPStatus.SEE_OTHER
        length = f.seek(0, 2)
        f.seek(0)
        headers = {
                'Content-Type':'text/plain;charset=utf-8',
                'Content-Length': length,
                'Location': '/'
            }
        
        return response, headers, f, lambda: None

class InvoiceEditor(BaseProvider):
    @staticmethod
    def get_content(handler, url, query={}, full_url=''):
        p = Path(__file__).parent / 'data/html/edit_invoice.html'
        f = p.read_text('utf-8')
        
        try:
            if is_integer(query.setdefault('id', [''])[0]):
                id_ = int(query.setdefault('id', [''])[0])
                invoice = handler.dbsession.query(Invoice).get(id_)
                if invoice is None:
                    raise ValueError
            else:
                cal = Config.get(
                    handler.dbsession, 'calendar', default='gregorian')
                year, month, day = multicalendar.today(cal)
                t = datetime.datetime.now().time()
                invoice = Invoice(id='', name='', year=year, month=month, day=day, t=t)
            
            q = handler.dbsession.query(
                Category.id, Category.name
            ).order_by(
                Category.name
            )
            categories = []
            for c in q:
                if c[0] != invoice.category_id:
                    categories.append('<option value="{0}">{1}</option>'.format(*c))
                else:
                    categories.append(
                        '<option value="{0}" selected>{1}</option>'.format(*c)
                    )
            
            minutes = []
            for c in range(60):
                if c != invoice.t.minute:
                    minutes.append('<option>{}</option>'.format(c))
                else:
                    minutes.append('<option selected>{}</option>'.format(c))
            
            hours = []
            for c in range(24):
                if c != invoice.t.hour:
                    hours.append('<option>{}</option>'.format(c))
                else:
                    hours.append('<option selected>{}</option>'.format(c))
            
            cal = Config.get(handler.dbsession, 'calendar', default='gregorian')
            last_month, last_day = multicalendar.date_values(cal)
            
            months = []
            for c in range(last_month):
                month = c + 1
                if month != invoice.month:
                    months.append('<option>{}</option>'.format(month))
                else:
                    months.append('<option selected>{}</option>'.format(month))
            
            days = []
            for c in range(last_day):
                day = c + 1
                if day != invoice.day:
                    days.append('<option>{}</option>'.format(day))
                else:
                    days.append('<option selected>{}</option>'.format(day))
            
            incomes = []
            expenses = []
            item_template = '\n'.join((
                '<tr>',
                '<td>',
                '<button class="button large-text" onclick="remove_row(this);">??????</button>',
                '</td>',
                '<td>',
                '<input name="item-{0.id}-name" form="invoice_form" placeholder="?????? ??????????" class="default-input" value="{0.name}">',
                '</td>',
                '<td>',
                '<input name="item-{0.id}-{2}" form="invoice_form" type="number" min="0" step="0.01" placeholder="????????????" class="default-input" value="{1}">',
                '</td>',
                '<td>',
                '<input name="item-{0.id}-remark" form="invoice_form" placeholder="??????????????" class="default-input" value="{0.remark}">',
                '</td>',
                '</tr>'
            ))
            for item in sorted(invoice.items, key=lambda c: abs(c.value)):
                if item.value >= 0:
                    incomes.append(
                        item_template.format(
                            item, '{:0.2f}'.format(item.income), 'income'))
                else:
                    expenses.append(
                        item_template.format(
                            item, '{:0.2f}'.format(item.expense), 'expense'))
            
            categories = '\n'.join(categories)
            months = '\n'.join(months)
            days = '\n'.join(days)
            hours = '\n'.join(hours)
            minutes = '\n'.join(minutes)
            incomes = '\n'.join(incomes)
            expenses = '\n'.join(expenses)
            template = '<input type="hidden" name="invoice_id" value="{}">'
            invoice_id_input = template.format(invoice.id)
            
            f = f.format(
                invoice_id_input=invoice_id_input, invoice=invoice,
                incomes=incomes, expenses=expenses, categories=categories,
                months=months, days=days, hours=hours, minutes=minutes
            )
        except ValueError:
            return self.short_response(http.HTTPStatus.NOT_FOUND)
        
        response = http.HTTPStatus.OK
        headers = {}
        
        return response, headers, f, lambda: None
    
    @staticmethod
    def post_content(handler, url, query={}, full_url=''):
        l = int(handler.headers['Content-Length'])
        content_type, pdict = parse_header(handler.headers['Content-Type'])
        
        content = handler.rfile.read(l)
        stream = io.BytesIO(content)
        mp = multipart.MultipartParser(
            stream, pdict['boundary'], len(content), charset='utf8')
        
        content = {}
        
        for c in mp:
            if c.name not in content:
                content[c.name] = c.value
        
        cal = Config.get(handler.dbsession, 'calendar', default='gregorian')
        
        if content['invoice_id'] != '':
            invoice = handler.dbsession.query(Invoice).get(
                int(content['invoice_id']))
        else:
            invoice = Invoice()
            handler.dbsession.add(invoice)
        
        invoice.name = content['name']
        if content['category'] != '':
            invoice.category_id = int(content['category'])
        else:
            invoice.category_id = None
        
        year = int(content['year'])
        month = int(content['month'])
        day = int(content['day'])
        
        try:
            multicalendar.validate(year, month, day, calendar=cal)
        except ValueError:
            return BaseProvider.short_response(HTTPStatus.UNPROCESSABLE_ENTITY,
                body='Invalid date!')
        
        invoice.year = year
        invoice.month = month
        invoice.day = day
        invoice.t = datetime.time(
            hour=int(content['hour']), minute=int(content['minute']))
        
        old_items = [c.id for c in invoice.items]
        kept_items = set()
        items = {}
        for c in content:
            parts = c.split('-')
            if parts[0] == 'item':
                id_ = int(parts[1])
                idx = '{}_{}'.format(parts[0], id_)
                if idx not in items:
                    items[idx] = handler.dbsession.query(Item).get(id_)
                    kept_items.add(items[idx].id)
                
                if parts[2] in ('income', 'expense'):
                    content[c] = float(content[c])
                
                setattr(items[idx], parts[2], content[c])
            elif parts[0] in ('income', 'expense'):
                id_ = int(parts[1])
                idx = '{}_{}'.format(parts[0], id_)
                if idx not in items:
                    items[idx] = Item(invoice=invoice)
                    invoice.items.append(items[idx])
                
                if parts[2] in ('income', 'expense'):
                    content[c] = float(content[c])
                
                setattr(items[idx], parts[2], content[c])
        
        deleted_items = [c for c in old_items if c not in kept_items]
        for c in deleted_items:
            item = handler.dbsession.query(Item).get(c)
            handler.dbsession.delete(item)
        
        user_id = handler.session['user']
        users_session = handler.user_session
        user = users_session.query(User).filter(User.id==user_id).first()
        print(user)
        username = user.username
        
        mod = InvoiceModification(timestamp=time.time(), username=username,
            invoice=invoice)
        handler.dbsession.add(mod)
        
        handler.dbsession.commit()
        id_ = invoice.id
        
        f = io.BytesIO()
            
        response = http.HTTPStatus.SEE_OTHER
        length = f.seek(0, 2)
        f.seek(0)
        headers = {
                'Content-Type':'text/plain;charset=utf-8',
                'Content-Length': length,
                'Location': 'invoice?id={}'.format(id_)
            }
        
        return response, headers, f, lambda: None

class SettingsViewer(BaseProvider):
    @staticmethod
    def get_content(handler, url, query={}, full_url=''):
        p = Path(__file__).parent / 'data/html/settings.html'
        f = p.read_text('utf-8')
        
        response = http.HTTPStatus.OK
        headers = {}
        
        return response, headers, f, lambda: None

class DBLister(BaseProvider):
    def __init__(self, path):
        self.path = Path(path).resolve()
    
    def get_content(self, handler, url, query={}, full_url=''):
        template = (
            '<tr>' +
            '<td>' +
            '<div class="vertical-div">' + 
            '<button class="button" onclick="document.location.href = \'copy_db?current_dbname={0}\';">??????</button>' +
            '<button class="button" onclick="document.location.href = \'delete_db?current_dbname={0}\';">??????</button>' +
            '</div>' + 
            '</td>' +
            '<td onclick="change_db(&quot;{0}&quot;);">{0}</td>' +
            '</tr>'
        )
        
        p = self.path / 'db'
        
        db_list = []
        for c in p.iterdir():
            db_list.append(template.format(c.stem))
        
        db_list.sort()
        
        p = Path(__file__).parent / 'data/html/db_list.html'
        f = p.read_text('utf-8').format(db_list='\n'.join(db_list))
        
        response = http.HTTPStatus.OK
        headers = {}
        
        return response, headers, f, lambda: None

class DBChanger(BaseProvider):
    def __init__(self, path):
        self.path = Path(path).resolve()
    
    def post_content(self, handler, url, query={}, full_url=''):
        l = int(handler.headers['Content-Length'])
        content_type, pdict = parse_header(handler.headers['Content-Type'])
        
        content = handler.rfile.read(l)
        stream = io.BytesIO(content)
        mp = multipart.MultipartParser(
            stream, pdict['boundary'], len(content), charset='utf8')
        
        content = {}
        
        for c in mp:
            if c.name not in content:
                content[c.name] = c.value
        
        db_path = self.path / 'db' / '{}.sqlite3'.format(
            content['dbname'])
        set_engine(handler, db_path)
        
        f = io.BytesIO()
            
        response = http.HTTPStatus.SEE_OTHER
        length = f.seek(0, 2)
        f.seek(0)
        headers = {
                'Content-Type':'text/plain;charset=utf-8',
                'Content-Length': length,
                'Location': '/'
            }
        
        return response, headers, f, lambda: None
    

class DBCopier(BaseProvider):
    def __init__(self, path):
        self.path = Path(path).resolve()
    
    def get_content(self, handler, url, query={}, full_url=''):
        p = Path(__file__).parent / 'data/html/copy_db.html'
        f = p.read_text('utf-8')
        template = '<input type="hidden" name="current_dbname" value="{}">'
        dbname_element = template.format(query['current_dbname'][0])
        
        f = f.format(current_dbname=dbname_element)
        
        response = http.HTTPStatus.OK
        headers = {}
        
        return response, headers, f, lambda: None
    
    def post_content(self, handler, url, query={}, full_url=''):
        l = int(handler.headers['Content-Length'])
        content_type, pdict = parse_header(handler.headers['Content-Type'])
        
        content = handler.rfile.read(l)
        stream = io.BytesIO(content)
        mp = multipart.MultipartParser(
            stream, pdict['boundary'], len(content), charset='utf8')
        
        content = {}
        
        for c in mp:
            if c.name not in content:
                content[c.name] = c.value
        
        pin = self.path / 'db' / '{}.sqlite3'.format(
            content['current_dbname'])
        pout = self.path / 'db' / '{}.sqlite3'.format(content['dbname'])
        backup(pin, pout)
        set_engine(handler, pout)
        
        f = io.BytesIO()
            
        response = http.HTTPStatus.SEE_OTHER
        length = f.seek(0, 2)
        f.seek(0)
        headers = {
                'Content-Type':'text/plain;charset=utf-8',
                'Content-Length': length,
                'Location': '/'
            }
        
        return response, headers, f, lambda: None

class CategoryEditor(BaseProvider):
    @staticmethod
    def get_content(handler, url, query={}, full_url=''):
        p = Path(__file__).parent / 'data/html/edit_categories.html'
        f = p.read_text('utf-8')
        template = (
            '<tr>'
            '<td>'
            '<input form="save_form" placeholder="?????? ??????????????" name="cat_{0.id}" value="{0.name}" class="default-input"/>'
            '</td>'
            '<td>'
            '<button class="button" onclick="remove_row(this)">??????</button>'
            '</td>'
            '</tr>'
        )
        
        category_list = []
        q = handler.dbsession.query(Category).order_by(Category.name).all()
        for c in q:
            category_list.append(template.format(c))
        
        f = f.format(category_list='\n'.join(category_list))
        
        response = http.HTTPStatus.OK
        headers = {}
        
        return response, headers, f, lambda: None
    
    @staticmethod
    def post_content(handler, url, query={}, full_url=''):
        l = int(handler.headers['Content-Length'])
        content_type, pdict = parse_header(handler.headers['Content-Type'])
        
        content = handler.rfile.read(l)
        stream = io.BytesIO(content)
        mp = multipart.MultipartParser(
            stream, pdict['boundary'], len(content), charset='utf8')
        
        content = {}
        
        for c in mp:
            if c.name not in content:
                content[c.name] = c.value
        
        for c in content:
            prefix, id_ = c.split('_')
            id_ = int(id_)
            if prefix == 'cat' and content[c]:
                cat = handler.dbsession.query(Category).get(id_)
                cat.name = content[c]
            elif prefix == 'new' and content[c]:
                cat = Category(name=content[c])
                handler.dbsession.add(cat)
        
        handler.dbsession.commit()
        
        f = io.BytesIO()
            
        response = http.HTTPStatus.SEE_OTHER
        length = f.seek(0, 2)
        f.seek(0)
        headers = {
                'Content-Type':'text/plain;charset=utf-8',
                'Content-Length': length,
                'Location': '/'
            }
        
        return response, headers, f, lambda: None

class BackupCreator(BaseProvider):
    def __init__(self, path):
        self.path = Path(path).resolve()
    
    def get_content(self, handler, url, query={}, full_url=''):
        p = Path(__file__).parent / 'data/html/create_backup.html'
        f = p.read_text('utf-8')
        template = '<option value="{0}">{1}</option>'
        
        p = self.path / 'backup/named/'
        p.mkdir(parents=True, exist_ok=True)
        
        dbname = Path(handler.session['dbname']).stem
        cal = Config.get(handler.dbsession, 'calendar', default='gregorian')
        backup_list = []
        for c in p.iterdir():
            c = c.stem.split('_')
            if c[0] == dbname:
                c[2] = multicalendar.fromtimestamp(int(c[2]), cal)
                c[2][-1] = int(c[2][-1])
                backup_list.append(c)
        
        backup_list_html = []
        for c in sorted(backup_list, key=lambda arg: arg[2]):
            option_text = '{0} - {1[0]}-{1[1]}-{1[2]} {1[3]:02}:{1[4]:02}:{1[5]:02}'.format(c[1], c[2])
            backup_list_html.append(template.format(c[1], option_text))
        
        f = f.format(backup_list='\n'.join(backup_list_html))
        
        response = http.HTTPStatus.OK
        headers = {}
        
        return response, headers, f, lambda: None
    
    def post_content(self, handler, url, query={}, full_url=''):
        l = int(handler.headers['Content-Length'])
        content_type, pdict = parse_header(handler.headers['Content-Type'])
        
        content = handler.rfile.read(l)
        stream = io.BytesIO(content)
        mp = multipart.MultipartParser(
            stream, pdict['boundary'], len(content), charset='utf8')
        
        content = {}
        
        for c in mp:
            if c.name not in content:
                content[c.name] = c.value
        
        if 'replace' in content:
            backup_name = content['backup-name-replace']
        else:
            backup_name = content['backup-name']
        
        backup_dir = self.path / 'backup/named'
        backup_dir.mkdir(parents=True, exist_ok=True)
        dbname = Path(handler.session['dbname']).stem
        t = int(time.time())
        backup_file_name = '{}_{}_{}.sqlite3'.format(dbname, backup_name, t)
        backup_path = backup_dir / backup_file_name
        
        dbpath = self.path / 'db' / '{}'.format(
            handler.session['dbname'])
        backup(dbpath, backup_path)
        
        if 'replace' in content:
            for c in backup_dir.iterdir():
                if c != backup_path:
                    parts = c.name.split('_')
                    if parts[0] == dbname and parts[1] == backup_name:
                        c.unlink()
        
        f = io.BytesIO()
            
        response = http.HTTPStatus.SEE_OTHER
        length = f.seek(0, 2)
        f.seek(0)
        headers = {
                'Content-Type':'text/plain;charset=utf-8',
                'Content-Length': length,
                'Location': ''
            }
        
        return response, headers, f, lambda: None

class BackupRestorer(BaseProvider):
    def __init__(self, path):
        self.path = Path(path).resolve()
    
    def get_content(self, handler, url, query={}, full_url=''):
        p = Path(__file__).parent / 'data/html/restore_backup.html'
        f = p.read_text('utf-8')
        template = '<option value="{0}">{1}</option>'
        
        dbname = Path(handler.session['dbname']).stem
        cal = Config.get(handler.dbsession, 'calendar', default='gregorian')
        
        p = self.path / 'backup/auto/'
        p.mkdir(parents=True, exist_ok=True)
        
        backup_list = []
        for c in p.iterdir():
            c = [c.name] + c.stem.split('_')
            if c[1] == dbname:
                c[2] = multicalendar.fromtimestamp(int(c[2]), cal)
                c[2][-1] = int(c[2][-1])
                backup_list.append(c)
        
        auto_backup_html = []
        for c in sorted(backup_list, key=lambda arg: arg[2], reverse=True):
            option_text = '{}-{}-{} {:02}:{:02}:{:02}'.format(*c[2])
            auto_backup_html.append(template.format(c[0], option_text))
        
        p = self.path / 'backup/named/'
        p.mkdir(parents=True, exist_ok=True)
        
        backup_list = []
        for c in p.iterdir():
            c = [c.name] + c.stem.split('_')
            if c[1] == dbname:
                c[3] = multicalendar.fromtimestamp(int(c[3]), cal)
                c[3][-1] = int(c[3][-1])
                backup_list.append(c)
        
        named_backup_html = []
        for c in sorted(backup_list, key=lambda arg: arg[3], reverse=True):
            option_text = '{0} - {1[0]}-{1[1]}-{1[2]} {1[3]:02}:{1[4]:02}:{1[5]:02}'.format(c[2], c[3])
            named_backup_html.append(template.format(c[0], option_text))
        
        f = f.format(
            dbname=dbname,
            auto_backup_list='\n'.join(auto_backup_html),
            named_backup_list='\n'.join(named_backup_html)
        )
        
        response = http.HTTPStatus.OK
        headers = {}
        
        return response, headers, f, lambda: None

class PostBackupRestorer(BaseProvider):
    def __init__(self, path):
        self.path = Path(path).resolve()
    
    def post_content(self, handler, url, query={}, full_url=''):
        l = int(handler.headers['Content-Length'])
        content_type, pdict = parse_header(handler.headers['Content-Type'])
        
        content = handler.rfile.read(l)
        stream = io.BytesIO(content)
        mp = multipart.MultipartParser(
            stream, pdict['boundary'], len(content), charset='utf8')
        
        content = {}
        
        for c in mp:
            if c.name not in content:
                content[c.name] = c.value
        
        if 'auto-backup' in content:
            backup_path = self.path / 'backup/auto' / content['auto-backup']
        else:
            backup_path = self.path / 'backup/named' / content['named-backup']
        
        dbname = '{}.sqlite3'.format(content['dbname'])
        dbpath = self.path / 'db' / dbname
        
        
        with DBSelector.locker.block_inc(dbname):
            DBSelector.locker.until_empty(dbname)
            backup(backup_path, dbpath)
        
        f = io.BytesIO()
            
        response = http.HTTPStatus.SEE_OTHER
        length = f.seek(0, 2)
        f.seek(0)
        headers = {
                'Content-Type':'text/plain;charset=utf-8',
                'Content-Length': length,
                'Location': '/'
            }
        
        return response, headers, f, lambda: None

class DBDownloader(BaseProvider):
    @staticmethod
    def get_content(handler, url, query={}, full_url=''):
        p = Path(__file__).parent / 'data/html/download.html'
        f = p.read_text('utf-8')
        
        dbname = Path(handler.session['dbname']).stem
        sqlite_name = '{}.sqlite3'.format(dbname)
        xlsx_name = '{}.xlsx'.format(dbname)
        
        f = f.format(dbname=dbname, sqlite_name=sqlite_name,
            xlsx_name=xlsx_name)
        response = http.HTTPStatus.OK
        headers = {}
        
        return response, headers, f, lambda: None

class XLSXDownloader(BaseProvider):
    @staticmethod
    def get_content(handler, url, query={}, full_url=''):
        f = tempfile.TemporaryFile()
        write_xlsx(handler.dbsession, f)
        
        response = http.HTTPStatus.OK
        length = f.seek(0, 2)
        f.seek(0)
        headers = {
            'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'Content-Length': length
        }
        
        return response, headers, f, lambda: None

class CSVDownloader(BaseProvider):
    @staticmethod
    def get_content(handler, url, query={}, full_url=''):
        f = CSVConverter(handler.dbsession)
        
        response = http.HTTPStatus.OK
        headers = {
            'Content-Type':'text/csv',
        }
        
        return response, headers, f, lambda: None

class SQLiteDownloader(BaseProvider):
    def __init__(self, path):
        self.path = Path(path).resolve()
    
    def get_content(self, handler, url, query={}, full_url=''):
        db_path = self.path / 'db' / handler.session['dbname']
        tmp_handle, tmp_path = tempfile.mkstemp()
        try:
            open(tmp_handle).close()
            backup(db_path, tmp_path)
            
            p = Path(tmp_path)
            f = p.open('br')
            
            response = http.HTTPStatus.OK
            length = f.seek(0, 2)
            f.seek(0)
            headers = {
                'Content-Type':'application/vnd.sqlite3',
                'Content-Length': length
            }
            
            return response, headers, f, lambda: p.unlink()
        except:
            Path(tmp_path).unlink()

class SQLiteUploader(BaseProvider):
    def __init__(self, path):
        self.path = Path(path)
    
    @staticmethod
    def get_content(handler, url, query={}, full_url=''):
        p = Path(__file__).parent / 'data/html/upload.html'
        
        f = p.read_text('utf-8')
        
        response = http.HTTPStatus.OK
        headers = {
        }
        
        return response, headers, f, lambda: None
    
    def post_content(self, handler, url, query={}, full_url=''):
        l = int(handler.headers['Content-Length'])
        content_type, pdict = parse_header(handler.headers['Content-Type'])
        
        content = handler.rfile.read(l)
        stream = io.BytesIO(content)
        mp = multipart.MultipartParser(
            stream, pdict['boundary'], len(content), charset='utf8')
        
        content = {}
        
        for c in mp:
            if c.name not in content:
                if c.filename or c.content_type:
                    content[c.name] = c.raw
                else:
                    content[c.name] = c.value
        
        data = content['dbfile']
        
        dbpath = self.path / 'db' / '{}'.format(
            handler.session['dbname'])
        
        with DBSelector.locker.block_inc(dbname):
            DBSelector.locker.until_empty(dbname)
            backup(data, dbpath)
        
        f = io.BytesIO()
            
        response = http.HTTPStatus.SEE_OTHER
        length = f.seek(0, 2)
        f.seek(0)
        headers = {
                'Content-Type':'text/plain;charset=utf-8',
                'Content-Length': length,
                'Location': '/settings'
            }
        
        return response, headers, f, lambda: None

class DBDeleter(BaseProvider):
    def __init__(self, path):
        self.path = Path(path)
    
    @staticmethod
    def get_content(handler, url, query={}, full_url=''):
        p = Path(__file__).parent / 'data/html/delete.html'
        f = p.read_text('utf-8')
        
        name = query['current_dbname'][0]
        message = '?????? ?????????? ???????????????? {}??'.format(name)
        inputs = '<input type="hidden" name="dbname" value="{}">'.format(name)
        back_url = 'db_list'
        f = f.format(message=message, inputs=inputs, back_url=back_url)
        
        response = http.HTTPStatus.OK
        headers = {}
        
        return response, headers, f, lambda: None
    
    def post_content(self, handler, url, query={}, full_url=''):
        l = int(handler.headers['Content-Length'])
        content_type, pdict = parse_header(handler.headers['Content-Type'])
        
        content = handler.rfile.read(l)
        stream = io.BytesIO(content)
        mp = multipart.MultipartParser(
            stream, pdict['boundary'], len(content), charset='utf8')
        
        content = {}
        
        for c in mp:
            if c.name not in content:
                content[c.name] = c.value
        
        dbname = '{}.sqlite3'.format(content['dbname'])
        dbpath = self.path / 'db' / dbname
        with DBSelector.locker.block_inc(dbname):
            DBSelector.locker.until_empty(dbname)
            dbpath.unlink()
        
        f = io.BytesIO()
            
        response = http.HTTPStatus.SEE_OTHER
        length = f.seek(0, 2)
        f.seek(0)
        headers = {
                'Content-Type':'text/plain;charset=utf-8',
                'Content-Length': length,
                'Location': '/'
            }
        
        return response, headers, f, lambda: None

class Reporter(BaseProvider):
    @staticmethod
    def get_content(handler, url, query={}, full_url=''):
        p = Path(__file__).parent / 'data/html/report.html'
        
        f = p.read_text('utf-8')
        
        cal = Config.get(handler.dbsession, 'calendar', default='gregorian')
        last_month, last_day = multicalendar.date_values(cal)
        
        years = []
        months = []
        
        for c in range(last_month):
            months.append('<option>{}</option>'.format(c+1))
        
        fy = handler.dbsession.query(
                Invoice.year
            ).order_by(
                Invoice.year
            ).first()
        
        ly = handler.dbsession.query(
                Invoice.year
            ).order_by(
                Invoice.year.desc()
            ).first()
        
        if fy is not None and ly is not None:
            fy = fy[0]
            ly = ly[0]
            for c in range(fy, ly+1):
                years.append('<option>{}</option>'.format(c))
        
        f = f.format(years=years, months=months)
        
        response = http.HTTPStatus.OK
        headers = {}
        
        return response, headers, f, lambda: None

class ReportGetter(BaseProvider):
    @classmethod
    def get_content(cls, handler, url, query={}, full_url=''):
        for c in query:
            query[c] = query[c][0]
        
        invoice_month = Invoice.year_month.label('invoice_month')
        q = cls.query(handler)
        
        if is_integer(query.setdefault('category', '')):
            q = q.filter(Category.id == int(query['category']))
        if (
                query.setdefault('year0', '').isdigit() and
                query.setdefault('month0', '').isdigit()
        ):
            month0 = (
                int(query['year0']),
                int(query['month0']),
            )
            month0 = '{:04}-{:02}'.format(*month0)
            q = q.filter(invoice_month >= month0)
        if (
                query.setdefault('year1', '').isdigit() and
                query.setdefault('month1', '').isdigit()
        ):
            month1 = (
                int(query['year1']),
                int(query['month1']),
            )
            month1 = '{:04}-{:02}'.format(*month1)
            q = q.filter(invoice_month <= month1)
        
        if query.setdefault('categorize', '') == 'true':
            q = q.group_by(None).group_by('invoice_month', Category.id)
        
        last_month = [int(c) for c in q.first()[0].split('-')]
        last_month[1] -= 1
        
        if query['categorize'] == 'true':
            out = {'results': {}, 'categories': {}}
            for c in q:
                current_month = [int(c) for c in c[0].split('-')]
                while current_month > last_month:
                    last_month[1] += 1
                    if last_month[1] > 12:
                        last_month[1] = 1
                        last_month[0] += 1
                    out['results']['{}-{:02}'.format(*last_month)] = {}
                month_dict = out['results'][c[0]]
                month_dict[c[1]] = c[3], c[4]
                if c[1] not in out['categories']:
                    out['categories'][c[1]] = c[2]
                
                last_month = current_month
            
            sorted_categories = sorted(out['categories'],
                key=lambda x: out['categories'][x])
            out['categories'] = [
                (c, out['categories'][c]) for c in sorted_categories]
        else:
            out = {'results': {}, 'categories': ['']}
            for c in q:
                current_month = [int(c) for c in c[0].split('-')]
                while current_month > last_month:
                    last_month[1] += 1
                    if last_month[1] > 12:
                        last_month[1] = 1
                        last_month[0] += 1
                    out['results']['{}-{:02}'.format(*last_month)] = 0, 0
                out['results'][c[0]] = c[3], c[4]
        
        if query.setdefault('gregorian', False):
            cal = Config.get(handler.dbsession, 'calendar', default='gregorian')
            if query['year0'].isdigit() and query['month0'].isdigit():
                d = [int(query['year0']), int(query['month0']), 1]
                out['gregorian0'] = multicalendar.to_gregorian(*d, cal)
            if query['year1'].isdigit() and query['month1'].isdigit():
                d = [int(query['year1']), int(query['month1'])]
                d.append(multicalendar.month_length(*d, cal))
                out['gregorian1'] = multicalendar.to_gregorian(*d, cal)
            
        page = json.dumps(out)
        
        f = io.BytesIO(page.encode('utf8'))
        
        length = f.seek(0, 2)
        f.seek(0)
        headers = {
            'Content-Type': 'application/json;charset=utf-8',
            'Content-Length': length
        }
        
        response = http.HTTPStatus.OK
        
        return response, headers, f, lambda: None

    @staticmethod
    def query(handler):
        invoice_month = Invoice.year_month.label('invoice_month')
        income = func.sum(Item.income).label('income')
        expense = func.sum(Item.expense).label('expense')
        q = handler.dbsession.query(
                invoice_month, Category.id, func.ifnull(Category.name, ''),
                income, expense
            ).outerjoin(
                Invoice.category
            ).outerjoin(
                Invoice.items
            ).group_by(
                'invoice_month'
            )
        return q

class BalanceGetter(BaseProvider):
    @classmethod
    def get_content(cls, handler, url, query={}, full_url=''):
        for c in query:
            query[c] = query[c][0]
        
        if query.setdefault('exclusive', '') == '1':
            op = operator.lt
        else:
            op = operator.le
        
        q = handler.dbsession.query(func.sum(Item.value))
        if query.setdefault('year', '').isdigit():
            query['year'] = int(query['year'])
            if query.setdefault('month', '').isdigit():
                query['month'] = int(query['month'])
                if query.setdefault('day', '').isdigit():
                    query['day'] = int(query['day'])
                    year_day = '{:04}-{:02}-{02}'.format(
                        query['year'], query['month'], query['day'])
                    q = q.join(Item.invoice).filter(
                        op(Invoice.date, year_day))
                else:
                    year_month = '{:04}-{:02}'.format(
                        query['year'], query['month'])
                    q = q.join(Item.invoice).filter(
                        op(Invoice.year_month, year_month))
            else:
                q = q.join(Item.invoice).filter(
                    op(Invoice.year, int(query['year'])))
        
        out = q.scalar()
        if out is None:
            out = 0
        page = json.dumps(out)
        
        f = io.BytesIO(page.encode('utf8'))
        
        length = f.seek(0, 2)
        f.seek(0)
        headers = {
            'Content-Type': 'application/json;charset=utf-8',
            'Content-Length': length
        }
        
        response = http.HTTPStatus.OK
        
        return response, headers, f, lambda: None

class Quitter(BaseProvider):
    @staticmethod
    def post_content(handler, url, query={}, full_url=''):
        p = Path(__file__).parent / 'data/html/quit.html'
        f = p.open('br')
            
        response = http.HTTPStatus.OK
        length = f.seek(0, 2)
        f.seek(0)
        headers = {
                'Content-Type':'text/html;charset=utf-8',
                'Content-Length': length,
            }
        return response, headers, f, handler.server.shutdown

class Loginner(BaseProvider):
    def __init__(self, engine):
        self.engine = engine
    
    @staticmethod
    def get_content(handler, url, query={}, full_url=''):
        p = Path(__file__).parent / 'data/html/login.html'
        
        f = p.read_text('utf-8')
        
        if 'failed' not in query:
          f = f.replace('{{failed_text}}', '')
        else:
          f = f.replace('{{failed_text}}', '<label class="default-label" style="color: red">?????? ????????????</label>')
        
        response = http.HTTPStatus.OK
        headers = {}
        
        return response, headers, f, lambda: None
    
    def post_content(self, handler, url, query={}, full_url=''):
        l = int(handler.headers['Content-Length'])
        content_type, pdict = parse_header(handler.headers['Content-Type'])
        
        content = handler.rfile.read(l)
        stream = io.BytesIO(content)
        mp = multipart.MultipartParser(
            stream, pdict['boundary'], len(content), charset='utf8')
        
        content = {}
        
        for c in mp:
            if c.name not in content:
                content[c.name] = c.value
        
        session = Session(self.engine)
        
        q = session.query(User)
        q = q.filter(User.username == content['username'])
        user = q.one_or_none()
        if user is None:
          f = io.BytesIO()
          
          response = http.HTTPStatus.SEE_OTHER
          length = f.seek(0, 2)
          f.seek(0)
          headers = {
                  'Content-Type':'text/plain;charset=utf-8',
                  'Content-Length': length,
                  'Location': '/login?failed=1'
              }
          
          return response, headers, f, lambda: None
        
        salted_password = content['password'].encode('utf8') + user.salt
        sha = hashlib.sha512()
        sha.update(salted_password)
        if user.password != sha.digest():
          f = io.BytesIO()
          
          response = http.HTTPStatus.SEE_OTHER
          length = f.seek(0, 2)
          f.seek(0)
          headers = {
                  'Content-Type':'text/plain;charset=utf-8',
                  'Content-Length': length,
                  'Location': '/login?failed=1'
              }
          
          return response, headers, f, lambda: None
        
        handler.session['user'] = user.id
        
        f = io.BytesIO()
            
        response = http.HTTPStatus.SEE_OTHER
        length = f.seek(0, 2)
        f.seek(0)
        headers = {
                'Content-Type':'text/plain;charset=utf-8',
                'Content-Length': length,
                'Location': '/'
            }
        
        return response, headers, f, lambda: None

class UserChecker(BaseProvider):
    def __init__(self, engine, provider, url):
        self.engine = engine
        self.provider = provider
        self.url = url
    
    def check_user(self, handler):
        return 'user' in handler.session and self.check_db_user(handler)
    
    def check_db_user(self, handler):
        user_id = handler.session['user']
        session = Session(self.engine)
        return session.query(User).filter(User.id==user_id).count() > 0
    
    def get_content(self, handler, *args, **kwargs):
        if self.check_user(handler):
            handler.user_session = Session(self.engine)
            return self.provider.get_content(handler, *args, **kwargs)
        else:
            f = io.BytesIO()
            
            response = http.HTTPStatus.SEE_OTHER
            length = f.seek(0, 2)
            f.seek(0)
            headers = {
                    'Content-Type':'text/plain;charset=utf-8',
                    'Content-Length': length,
                    'Location': '/login'
                }
            
            return response, headers, f, lambda: None
    
    def post_content(self, handler, *args, **kwargs):
        if self.check_user(handler):
            handler.user_session = Session(self.engine)
            return self.provider.post_content(handler, *args, **kwargs)
        else:
            f = io.BytesIO()
            
            response = http.HTTPStatus.SEE_OTHER
            length = f.seek(0, 2)
            f.seek(0)
            headers = {
                    'Content-Type':'text/plain;charset=utf-8',
                    'Content-Length': length,
                    'Location': '/login'
                }
            
            return response, headers, f, lambda: None

