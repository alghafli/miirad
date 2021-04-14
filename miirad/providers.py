from cofan import BaseProvider, BaseHandler, Patterner
from http import cookies
import random
from pathlib import Path
from sqlalchemy import create_engine, desc, asc
from sqlalchemy.orm import Session
from .utils import partial_caller
from .db import *
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
import shutil

def is_integer(v):
    try:
        int(v)
        return True
    except ValueError:
        return False

def copy_db(f, new_f):
    engine = create_engine('sqlite:///{}'.format(f))
    with engine.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        shutil.copy(f, new_f)

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
    def __init__(self, path, provider):
        self.path = Path(path).resolve()
        self.provider = provider
    
    def get_content(self, handler, url, query={}, full_url=''):
        try:
            if 'dbengine' not in handler.session:
                p = Path(self.path) / 'db'
                p.mkdir(parents=True, exist_ok=True)
                dbs = list(p.iterdir())
                if dbs:
                    latest_db = max(dbs, key=lambda p: p.stat().st_atime)
                    engine = create_engine('sqlite:///{}'.format(latest_db))
                    handler.session['dbengine'] = engine
                    handler.session['dbname'] = latest_db.name
                else:
                    raise FileNotFoundError
            
            handler.dbsession = Session(handler.session['dbengine'])
            
            response, headers, f, postproc = \
                self.provider.get_content(handler, url, query, full_url)
            postproc = partial_caller(handler.dbsession.close, postproc)
            
            return response, headers, f, postproc
        except Exception:
            print(traceback.format_exc())
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
        try:
            if 'dbengine' not in handler.session:
                p = Path(self.path) / 'db'
                p.mkdir(parents=True, exist_ok=True)
                dbs = list(p.iterdir())
                if dbs:
                    latest_db = max(dbs, key=lambda p: p.stat().st_atime)
                    engine = create_engine('sqlite:///{}'.format(latest_db))
                    handler.session['dbengine'] = engine
                    handler.session['dbname'] = latest_db.name
                else:
                    raise FileNotFoundError
            
            handler.dbsession = Session(handler.session['dbengine'])
            
            response, headers, f, postproc = \
                self.provider.post_content(handler, url, query, full_url)
            postproc = partial_caller(handler.dbsession.close, postproc)
            
            return response, headers, f, postproc
        except Exception:
            print(traceback.format_exc())
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
            db_label = '<label class="default-label">{}</label>'.format(dbname)
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
        f = f.replace('{{years}}', '\n'.join(years))
        f = f.replace('{{months}}', '\n'.join(months))
        f = f.replace('{{days}}', '\n'.join(days))
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
                invoice_date.desc(), Invoice.t, Invoice.id
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
                income_template.format('مجموع الإيرادات', total_incomes))
            
            sums.append(
                expense_template.format('مجموع المصاريف', total_expenses))
            
            if total >= 0:
                sums.append(
                    income_template.format('المجموع الكلي', total))
            else:
                sums.append(
                    expense_template.format('المجموع الكلي', -total))
            
            incomes = '\n'.join(incomes)
            expenses = '\n'.join(expenses)
            sums = '\n'.join(sums)
            f = f.format(
                invoice=invoice, category=category,
                items=incomes+expenses+sums)
        except ValueError:
            return BaseProvider.short_response(http.HTTPStatus.NOT_FOUND)
        
        response = http.HTTPStatus.OK
        headers = {}
        
        return response, headers, f, lambda: None

class InvoiceDeleter(BaseProvider):
    @staticmethod
    def get_content(handler, url, query={}, full_url=''):
        p = Path(__file__).parent / 'data/html/delete_invoice.html'
        f = p.read_text('utf-8')
        
        f = f.format(id=query['id'][0])
        
        response = http.HTTPStatus.OK
        headers = {}
        
        return response, headers, f, lambda: None
    
    @staticmethod
    def post_content(handler, url, query={}, full_url=''):
        id_ = query['id'][0]
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
                '<button class="button large-text" style="background: #BBBBBB;" onclick="remove_row(this);">حذف</button>',
                '</td>',
                '<td>',
                '<input name="item-{0.id}-name" form="invoice_form" placeholder="اسم البند" class="default-input" value="{0.name}">',
                '</td>',
                '<td>',
                '<input name="item-{0.id}-{2}" form="invoice_form" type="number" min="0" step="0.01" placeholder="القيمة" class="default-input small-input" value="{1}">',
                '</td>',
                '<td>',
                '<input name="item-{0.id}-remark" form="invoice_form" placeholder="ملاحظات" class="default-input" value="{0.remark}">',
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

class DbLister(BaseProvider):
    def __init__(self, path):
        self.path = Path(path).resolve()
    
    def get_content(self, handler, url, query={}, full_url=''):
        template = (
            '<tr>' +
            '<td>' +
            '<button class="button" style="background: #BBBBBB;" form="change_db_form" type="submit" name="dbname" value="{0}">اختر</button>' +
            '<br>' +
            '<button class="button" style="background: #BBBBBB; text-align: center;" onclick="document.location.href = \'copy_db?current_dbname={0}\';">نسخ</button>' +
            '<br>' +
            '<button class="button" style="background: #BBBBBB; text-align: center;" onclick="document.location.href = \'delete_db?current_dbname={0}\';">حذف</button>' +
            '</td>' +
            '<td>{0}</td>' +
            '</tr>'
        )
        
        p = Path(self.path) / 'db'
        
        db_list = []
        for c in p.iterdir():
            db_list.append(template.format(c.stem))
        
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
        
        db_path = Path(self.path) / 'db' / '{}.sqlite3'.format(
            content['dbname'])
        engine = create_engine('sqlite:///{}'.format(db_path))
    
        handler.session['dbengine'] = engine
        handler.session['dbname'] = db_path.name
        
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
        
        pin = Path(self.path) / 'db' / '{}.sqlite3'.format(
            content['current_dbname'])
        pout = Path(self.path) / 'db' / '{}.sqlite3'.format(content['dbname'])
        copy_db(pin, pout)
        engine = create_engine('sqlite:///{}'.format(pout))
    
        handler.session['dbengine'] = engine
        handler.session['dbname'] = pout.name
        
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
            '<input form="save_form" placeholder="Category Name" name="cat_{0.id}" value="{0.name}" class="default-input"/>'
            '</td>'
            '<td>'
            '<button class="button" style="background: #BBBBBB;" onclick="remove_row(this)">حذف</button>'
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
    
