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

import pytest
import time
import pretend
import redis
from armonaut.utils import crypto
from armonaut.sessions import InvalidSession, Session, RedisSessionFactory


@pytest.mark.parametrize(
    'method',
    ['__contains__',
     '__delitem__',
     '__getitem__',
     '__len__',
     '__iter__',
     '__setitem__',
     'clear',
     'copy',
     'fromkeys',
     'get',
     'items',
     'keys',
     'pop',
     'popitem',
     'setdefault',
     'update',
     'values',
     'invalidate',
     'flash',
     'changed',
     'get_csrf_token',
     'new_csrf_token',
     'pop_flash',
     'peek_flash',
     'should_save']
)
def test_invalid_session_methods(method):
    """Assert that InvalidSession can't have any methods
    called without an exception being raised.
    """
    session = InvalidSession()
    with pytest.raises(RuntimeError):
        getattr(session, method)()


@pytest.mark.parametrize(
    'prop',
    ['sid', 'created', 'new']
)
def test_invalid_session_properties(prop):
    """Assert that InvalidSession can't have any properties
    read without an exception being raised."""
    session = InvalidSession()
    with pytest.raises(RuntimeError):
        getattr(session, prop)


def test_create_new_timestamp(monkeypatch):
    """Assert that session.created is the UTC timestamp
    that it was created on.
    """
    monkeypatch.setattr(time, 'time', lambda: 100)

    session = Session({})

    assert session.created == 100


@pytest.mark.parametrize(
    ('data', 'expected'),
    [(None, {}),
     ({}, {}),
     ({'foo': 'bar'}, {'foo': 'bar'})]
)
def test_create_new_session_id(monkeypatch, data, expected):
    """Assert that when a new session is created that
    it's properties are correctly set.
    """
    monkeypatch.setattr(crypto, 'random_token', lambda: '12345678')

    session = Session(data)
    assert session == expected
    assert session.sid == '12345678'
    assert session.new
    assert not session.invalidated


def test_session_id_generated_once(monkeypatch):
    monkeypatch.setattr(crypto, 'random_token', pretend.call_recorder(func=lambda: '12345678'))

    session = Session({})
    assert session.sid == '12345678'
    assert session.sid == '12345678'

    assert crypto.random_token.calls == [pretend.call()]


def test_new_session_not_changed():
    """Assert that a session should not be saved on
    creation without modifications.
    """
    session = Session({'foo': 'bar'})

    assert not session.should_save()


@pytest.mark.parametrize(
    ('func', 'args', 'changed', 'expected'),
    [('__getitem__', ('foo',), False, {'foo': 'bar'}),
     ('__setitem__', ('foo', 'bar'), False, {'foo': 'bar'}),
     ('__setitem__', ('foo', 'bel'), True, {'foo': 'bel'}),
     ('__setitem__', ('bar', 'foo'), True, {'bar': 'foo', 'foo': 'bar'}),
     ('__delitem__', ('foo',), True, {}),
     ('setdefault', ('foo', 'bar'), False, {'foo': 'bar'}),
     ('setdefault', ('foo', 'bel'), False, {'foo': 'bar'}),
     ('setdefault', ('bar', 'foo'), True, {'foo': 'bar', 'bar': 'foo'})]
)
def test_session_changed(func, args, changed, expected):
    """Assert that if a session is changed that it should be saved and
    that the modifications occur correctly.
    """
    session = Session({'foo': 'bar'})
    getattr(session, func)(*args)

    assert session.should_save() == changed
    assert session == expected


def test_session_invalidated(monkeypatch):
    sids = iter(['1', '2'])
    monkeypatch.setattr(crypto, 'random_token', pretend.call_recorder(func=lambda: next(sids)))

    session = Session({'foo': 'bar'})
    assert session.sid == '1'

    session.invalidate()

    assert session.invalidated == {'1'}
    assert not session.changed()
    assert session.new
    assert session == {}

    assert session.sid == '2'
    assert crypto.random_token.calls == [pretend.call(), pretend.call()]


def test_session_invalidated_with_no_sid(monkeypatch):
    monkeypatch.setattr(crypto, 'random_token', pretend.call_recorder(func=lambda: '1'))
    session = Session()

    session.invalidate()

    assert session.invalidated == set([])
    assert session.sid == '1'
    assert crypto.random_token.calls == [pretend.call()]


def test_session_flash_message_no_queue():
    session = Session({})
    session.flash('message')

    assert session == {session._get_flash_queue_key(''): ['message']}
    assert session.should_save()


def test_session_flash_queue():
    session = Session({})
    session.flash('message', queue='queue')

    assert session == {session._get_flash_queue_key('queue'): ['message']}
    assert session.should_save()


def test_session_pop_flash_no_queue():
    session = Session({})
    session.flash('message1')
    session.flash('message2')

    assert session.pop_flash() == ['message1', 'message2']


def test_session_pop_flash_queues():
    session = Session({})
    session.flash('msg1', queue='queue1')
    session.flash('msg2', queue='queue2')

    assert session.pop_flash('queue1') == ['msg1']
    assert session.pop_flash('queue2') == ['msg2']


def test_session_peek_flash():
    session = Session({})
    session.flash('msg1')
    session.flash('msg2', queue='queue')

    assert session.peek_flash() == ['msg1']
    assert session.peek_flash() == ['msg1']

    assert session.peek_flash('queue') == ['msg2']
    assert session.peek_flash('queue') == ['msg2']


def test_session_flash_empty_queue():
    session = Session({})

    assert session.pop_flash() == []
    assert session.peek_flash() == []

    assert session.pop_flash('notfound') == []
    assert session.peek_flash('notfound') == []


@pytest.mark.parametrize('queue', ['', 'queue'])
def test_session_flash_allow_duplicates(queue):
    session = Session({})
    session.flash('message', queue=queue, allow_duplicate=True)
    session.flash('message', queue=queue, allow_duplicate=True)

    assert session.pop_flash(queue=queue) == ['message', 'message']


@pytest.mark.parametrize('queue', ['', 'queue'])
def test_session_flash_no_allow_duplicates(queue):
    session = Session({})
    session.flash('message', queue=queue, allow_duplicate=False)
    session.flash('message', queue=queue, allow_duplicate=False)

    assert session.pop_flash(queue=queue) == ['message']


def test_session_new_csrf_token(monkeypatch):
    monkeypatch.setattr(crypto, 'random_token', pretend.call_recorder(lambda: '12345678'))

    session = Session({})
    csrf_token = session.new_csrf_token()

    assert csrf_token == '12345678'
    assert session.should_save()


def test_session_get_csrf_token_before_new_csrf_token(monkeypatch):
    monkeypatch.setattr(crypto, 'random_token', pretend.call_recorder(lambda: '12345678'))

    session = Session({})
    csrf_token = session.get_csrf_token()

    assert csrf_token == '12345678'
    assert crypto.random_token.calls == [pretend.call()]


def test_session_get_csrf_token_after_new_csrf_token(monkeypatch):
    monkeypatch.setattr(crypto, 'random_token', pretend.call_recorder(lambda: '12345678'))

    session = Session({})
    csrf_token = session.new_csrf_token()

    assert csrf_token == session.get_csrf_token()
    assert csrf_token == '12345678'


def test_session_renew_csrf_token(monkeypatch):
    csrf_tokens = iter(['1', '2'])
    monkeypatch.setattr(crypto, 'random_token', pretend.call_recorder(lambda: next(csrf_tokens)))

    session = Session({})
    csrf1 = session.new_csrf_token()
    assert csrf1 == session.get_csrf_token()

    csrf2 = session.new_csrf_token()
    assert csrf2 == session.get_csrf_token()
    assert csrf1 != csrf2


def test_session_factory_init(monkeypatch):
    timestamp_signer_obj = pretend.stub()
    timestamp_signer_create = pretend.call_recorder(
        lambda secret, salt: timestamp_signer_obj
    )
    monkeypatch.setattr(crypto, 'TimestampSigner', timestamp_signer_create)

    strict_redis_obj = pretend.stub()
    strict_redis_cls = pretend.stub(
        from_url=pretend.call_recorder(lambda url: strict_redis_obj)
    )
    monkeypatch.setattr(redis, 'StrictRedis', strict_redis_cls)

    session_factory = RedisSessionFactory('secret', 'url')

    assert session_factory.signer is timestamp_signer_obj
    assert session_factory.redis is strict_redis_obj
    assert timestamp_signer_create.calls == [
        pretend.call('secret', salt='session')
    ]
    assert strict_redis_cls.from_url.calls == [
        pretend.call('url')
    ]


def test_redis_key():
    session_factory = RedisSessionFactory(
        'secret', 'redis://localhost:6479/0'
    )
    assert session_factory._redis_key('session_id') == 'armonaut/session/session_id'


def test_no_current_session(pyramid_request):
    session_factory = RedisSessionFactory(
        'secret', 'redis://localhost:6379/0'
    )
    session_factory._process_response = pretend.stub()
    session = session_factory(pyramid_request)

    assert len(pyramid_request.response_callbacks) == 1
    assert pyramid_request.response_callbacks[0] is session_factory._process_response
    assert isinstance(session, Session)
    assert session._sid is None
    assert session.new


def test_invalid_session_id(pyramid_request):
    pyramid_request.cookies['session'] = 'invalid'

    session_factory = RedisSessionFactory('secret', 'redis://localhost:6379/0')
    session_factory._process_response = pretend.stub()
    session = session_factory(pyramid_request)

    assert len(pyramid_request.response_callbacks) == 1
    assert pyramid_request.response_callbacks[0] is session_factory._process_response
    assert isinstance(session, Session)
    assert session._sid is None
    assert session.new
