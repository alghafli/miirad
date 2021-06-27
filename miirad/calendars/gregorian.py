import datetime
import calendar

DATE_VALUES = 12, 31

def validate(y, m, d):
    datetime.date(y, m, d)

def today():
    d = datetime.date.today()
    return d.year, d.month, d.day

def fromtimestamp(ts):
    d  = datetime.datetime.fromtimestamp(ts)
    return [d.year, d.month, d.day, d.hour, d.minute,
        d.second + d.microsecond / 1e6]

def from_gregorian(y, m, d):
    return y, m, d

def to_gregorian(y, m, d):
    return y, m, d

def month_length(y, m):
    return calendar.monthrange(y, m)[1]

