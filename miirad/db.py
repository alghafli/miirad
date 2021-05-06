from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, Text, Time, ForeignKey
from sqlalchemy import CheckConstraint
from sqlalchemy import func, case
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm.exc import NoResultFound
import json

Base = declarative_base()

class Category(Base):
    __tablename__ = 'category'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, CheckConstraint("name <> ''"), unique=True, index=True)
    
    invoices = relationship("Invoice", back_populates="category")
    
    def __repr__(self):
        return '<{t} {o.name}>'.format(
            t=type(self).__name__, o=self)


class Invoice(Base):
    __tablename__ = 'invoice'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, CheckConstraint("name <> ''"), index=True, nullable=False)
    category_id = Column(Integer, ForeignKey('category.id'))
    year = Column(Integer, nullable=False)
    month = Column(Integer, CheckConstraint("month between 1 and 12"), nullable=False)
    day = Column(Integer, CheckConstraint("day between 1 and 30"), nullable=False)
    t = Column(Time, nullable=False)
    
    category = relationship('Category')
    items = relationship("Item", back_populates="invoice", cascade='all, delete-orphan')
    
    @hybrid_property
    def date(self):
        return '{0.year:04}-{0.month:02}-{0.day:02}'.format(self)
    
    @date.expression
    def date(self):
        return func.substr('0000' + self.year.cast(Text), -4, 4) + '-' + \
            func.substr('00' + self.month.cast(Text), -2, 2) + '-' + \
            func.substr('00' + self.day.cast(Text), -2, 2)
    
    @hybrid_property
    def year_month(self):
        return '{0.year:04}-{0.month:02}'.format(self)
    
    @date.expression
    def year_month(self):
        return func.substr('0000' + self.year.cast(Text), -4, 4) + '-' + \
            func.substr('00' + self.month.cast(Text), -2, 2)
    
    
    def __repr__(self):
        return '<{t} {o.id} {o.name} {o.year}-{o.month}-{o.day} {o.t}>'.format(
            t=type(self).__name__, o=self)

class Item(Base):
    __tablename__ = 'Item'
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey('invoice.id'), nullable=False)
    name = Column(Text, CheckConstraint("name <> ''"), index=True, nullable=False)
    value = Column(Float, nullable=False)
    remark = Column(Text, nullable=False)
    
    invoice = relationship('Invoice')
    
    @hybrid_property
    def expense(self):
        if self.value < 0:
            return -self.value
    
    @expense.expression
    def expense(self):
        return case([(self.value < 0, -self.value)], else_=0)
    
    
    @expense.setter
    def expense(self, value):
        self.value = -value
    
    @hybrid_property
    def income(self):
        if self.value >= 0:
            return self.value
    
    @income.expression
    def income(self):
        return case([(self.value >= 0, self.value)], else_=0)
    
    @income.setter
    def income(self, value):
        self.value = value
    
    def __repr__(self):
        return '<{o.invoice.name} {o.name} {o.value}>'.format(o=self)

class Config(Base):
    __tablename__ = 'config'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, CheckConstraint("name <> ''"), index=True, nullable=False)
    _value = Column(Text)
    
    @property
    def value(self):
        return json.loads(self._value)
    
    @value.setter
    def value(self, new_value):
        self._value = json.dumps(new_value)
    
    @classmethod
    def get(cls, session, name, default=None):
        try:
            config = session.query(cls).filter_by(name=name).one()
            return config.value
        except NoResultFound:
            if default is not None:
                return default
            else:
                raise
    @classmethod
    def set(cls, session, name, value):
        try:
            config = session.query(cls).filter_by(name=name).one()
        except NoResultFound:
            config = cls(name=name)
            session.add(config)
            session.commit()
        
        config.value = value

