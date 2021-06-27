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

def from_gregorian(y, m, d):
    h = Gregorian(y, m, d).to_hijri()
    return h.year, h.month, h.day

def to_gregorian(y, m, d):
    g = Hijri(y, m, d).to_gregorian()
    return g.year, g.month, g.day

def month_length(y, m):
    return Hijri(y, m, 1).month_length()

