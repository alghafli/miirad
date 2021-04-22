from hijri_converter.convert import Hijri, Gregorian
import datetime

DATE_VALUES = 12, 30

def validate(y, m, d):
    Hijri(y, m, d)

def today():
    d = Gregorian.today().to_hijri()
    return d.datetuple()

def fromtimestamp(ts):
    d = datetime.datetime.fromtimestamp(ts)
    t = d.time()
    d = Gregorian.fromdate(d).to_hijri()
    return [d.year, d.month, d.day, t.hour, t.minute,
        t.second + t.microsecond / 1e6]

