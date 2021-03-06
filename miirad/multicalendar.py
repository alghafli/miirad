import datetime
import importlib

calendars = {}

def date_values(calendar='gregorian'):
    load_calendar(calendar)
    return calendars[calendar].DATE_VALUES

def validate(y, m, d, calendar='gregorian'):
    load_calendar(calendar)
    calendars[calendar].validate(y, m, d)

def today(calendar='gregorian'):
    load_calendar(calendar)
    return calendars[calendar].today()

def load_calendar(calendar):
    if calendar not in calendars:
        import_name = '.calendars.{}'.format(calendar)
        calendars[calendar] = importlib.import_module(import_name, 'miirad')

def fromtimestamp(ts, calendar='gregorian'):
    load_calendar(calendar)
    return calendars[calendar].fromtimestamp(ts)

def from_gregorian(y, m, d, calendar='gregorian'):
    load_calendar(calendar)
    return calendars[calendar].from_gregorian(y, m, d)

def to_gregorian(y, m, d, calendar='gregorian'):
    load_calendar(calendar)
    return calendars[calendar].to_gregorian(y, m, d)

def month_length(y, m, calendar='gregorian'):
    load_calendar(calendar)
    return calendars[calendar].month_length(y, m)

