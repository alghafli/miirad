from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Text, BLOB
from sqlalchemy import CheckConstraint

UsersBase = declarative_base()

class User(UsersBase):
    __tablename__ = 'user'
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(Text, CheckConstraint("username <> ''"), unique=True, index=True)
    password = Column(BLOB, CheckConstraint("username <> x''"))
    salt = Column(BLOB, CheckConstraint("username <> x''"))

