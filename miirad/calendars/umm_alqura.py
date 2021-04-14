from hijri_converter.convert import Hijri, Gregorian

DATE_VALUES = 12, 30

def validate(y, m, d):
    Hijri(y, m, d)

def today():
    d = Gregorian.today().to_hijri()
    return d.year, d.month, d.day

