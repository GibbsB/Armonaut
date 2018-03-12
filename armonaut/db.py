# Copyright 2018 Seth Michael Larson
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import functools
import alembic.config
import psycopg2.extensions
import sqlalchemy
import pyramid.request
import venusian
import zope.sqlalchemy
from sqlalchemy import event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from armonaut.utils.attrs import make_repr


__all__ = ['Model', 'Session', 'metadata']


DEFAULT_ISOLATION = 'READ COMMITTED'


class ReadOnlyPredicate:
    def __init__(self, val, config):
        self.val = val

    def text(self):
        return f'read_only = {self.val!r}'

    phash = text

    def __call__(self, info, request):
        return True


class ModelBase:
    def __repr__(self):
        self.__repr__ = make_repr(*self.__table__.columns.keys(), _self=self)
        return self.__repr__()


metadata = sqlalchemy.MetaData()
ModelBase = declarative_base(cls=ModelBase, metadata=metadata)


class Model(ModelBase):
    __abstract__ = True

    id = sqlalchemy.Column(
        sqlalchemy.BigInteger(),
        primary_key=True
    )


Session = sessionmaker()


def listens_for(target, identifier, *args, **kwargs):
    def deco(wrapped):
        def callback(scanner, _name, wrapped):
            wrapped = functools.partial(wrapped, scanner.config)
            event.listen(target, identifier, wrapped, *args, **kwargs)
        venusian.attach(wrapped, callback)
        return wrapped
    return deco


def _configure_alembic(config):
    alembic_config = alembic.config.Config()
    alembic_config.set_main_option('script_location', 'armonaut:migrations')
    alembic_config.set_main_option(
        'url', config.registry.settings['database.url']
    )
    return alembic_config


def _reset(dbapi_connection, connection_record):
    # If we set that the connection requires a reset
    # then restore the default isolation level of the connection
    # before releasing it back into the engine pool.
    needs_reset = connection_record.info.pop('armonaut.needs_reset', False)
    if needs_reset:
        dbapi_connection.set_session(
            isolation_level=DEFAULT_ISOLATION,
            readonly=False,
            deferrable=False
        )


def _create_engine(url: str):
    engine = sqlalchemy.create_engine(
        url,
        isolation_level=DEFAULT_ISOLATION,
        pool_size=35,
        max_overflow=65,
        pool_timeout=20
    )
    event.listen(engine, 'reset', _reset)
    return engine


def _create_session(request: pyramid.request.Request):
    connection = request.registry['sqlalchemy.engine'].connect()
    if (connection.connection.get_transaction_status() !=
            psycopg2.extensions.TRANSACTION_STATUS_IDLE):
        # Work-around for SQLAlchemy bug where the the initial
        # connection is left in the pool inside a transaction.
        connection.connection.rollback()

    # If it's a read-only request then the database
    # isolation level needs to be set.
    if request.read_only:
        connection.info['armonaut.needs_reset'] = True
        connection.connection.set_session(
            isolation_level='SERIALIZABLE',
            readonly=True,
            deferrable=True
        )

    session = Session(bind=connection)
    zope.sqlalchemy.register(session, transaction_manager=request.tm)

    @request.add_finished_callback
    def cleanup(_):
        session.close()
        connection.close()

    return session


def _readonly(request):
    if request.matched_route is not None:
        for predicate in request.matched_route.predicates:
            if isinstance(predicate, ReadOnlyPredicate) and predicate.val:
                return True
    return False


def includeme(config):
    config.add_directive('alembic_config', _configure_alembic)

    config.registry['sqlalchemy.engine'] = _create_engine(
        config.registry.settings['database.url']
    )
    config.add_request_method(_create_session, name='db', reify=True)

    config.add_route_predicate('read_only', ReadOnlyPredicate)
    config.add_request_method(_readonly, 'read_only', reify=True)
