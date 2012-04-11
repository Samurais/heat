# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
"""
SQLAlchemy models for heat data.
"""

from sqlalchemy import *
from sqlalchemy.orm import relationship, backref, object_mapper
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import ForeignKeyConstraint
from sqlalchemy import types as types
from json import dumps, loads
from nova import utils
from heat.db.sqlalchemy.session import get_session

BASE = declarative_base()

class Json(types.TypeDecorator, types.MutableType):
    impl=types.Text

    def process_bind_param(self, value, dialect):
        return dumps(value)

    def process_result_value(self, value, dialect):
        return loads(value)

class HeatBase(object):
    """Base class for Heat Models."""
    __table_args__ = {'mysql_engine': 'InnoDB'}
    __table_initialized__ = False
    created_at = Column(DateTime, default=utils.utcnow)
    updated_at = Column(DateTime, onupdate=utils.utcnow)

    def save(self, session=None):
        """Save this object."""
        if not session:
            session = get_session()
        session.add(self)
        try:
            session.flush()
        except IntegrityError, e:
            if str(e).endswith('is not unique'):
                raise exception.Duplicate(str(e))
            else:
                raise

    def delete(self, session=None):
        """Delete this object."""
        self.deleted = True
        self.deleted_at = utils.utcnow()
        self.save(session=session)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def __iter__(self):
        self._i = iter(object_mapper(self).columns)
        return self

    def next(self):
        n = self._i.next().name
        return n, getattr(self, n)

    def update(self, values):
        """Make the model object behave like a dict"""
        for k, v in values.iteritems():
            setattr(self, k, v)

    def iteritems(self):
        """Make the model object behave like a dict.

        Includes attributes from joins."""
        local = dict(self)
        joined = dict([(k, v) for k, v in self.__dict__.iteritems()
                      if not k[0] == '_'])
        local.update(joined)
        return local.iteritems()

class RawTemplate(BASE, HeatBase):
    """Represents an unparsed template which should be in JSON format."""

    __tablename__ = 'raw_template'
    id = Column(Integer, primary_key=True)
    template = Column(Json)
    parsed_template = relationship("ParsedTemplate",\
                                    uselist=False, backref="raw_template", cascade="all, delete", passive_deletes=True)

class ParsedTemplate(BASE, HeatBase):
    """Represents a parsed template."""

    __tablename__ = 'parsed_template'
    id = Column(Integer, primary_key=True) 
    template = Column(Json)
    raw_template_id = Column(Integer, ForeignKey('raw_template.id'),\
                            nullable=False)

class Stack(BASE, HeatBase):
    """Represents an generated by the heat engine."""

    __tablename__ = 'stack'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    raw_template_id = Column(Integer, ForeignKey('raw_template.id'),\
                            nullable=False)
    raw_template = relationship(RawTemplate,
        backref=backref('stack'), cascade="all, delete", passive_deletes=True)

class Event(BASE, HeatBase):
    """Represents an event generated by the heat engine."""

    __tablename__ = 'event'

    id = Column(Integer, primary_key=True)
    stack_id = Column(Integer, ForeignKey('stack.id'),\
                        nullable=False)
    stack = relationship(Stack,
        backref=backref('events'), cascade="all, delete", passive_deletes=True)
    
    name = Column(String)
 
class Resource(BASE, HeatBase):
    """Represents a resource created by the heat engine."""

    __tablename__ = 'resource'

    id = Column(Integer, primary_key=True)
    state = Column('state', String)
    name = Column('name', String, nullable=False)
    nova_instance = Column('nova_instance', String)
    state_description = Column('state_description', String)
    parsed_template_id = Column(Integer, ForeignKey('parsed_template.id'),\
                                 nullable=True)
    parsed_template = relationship(ParsedTemplate,        
        backref=backref('resources'))

    stack_id = Column(Integer, ForeignKey('stack.id'),\
                                 nullable=False)
    stack = relationship(Stack, backref=backref('resources'), cascade="all, delete", passive_deletes=True)

    depends_on = Column(Integer)