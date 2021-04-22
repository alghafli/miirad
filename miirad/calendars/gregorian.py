import datetime

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

