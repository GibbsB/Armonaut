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
import time
import msgpack
import msgpack.exceptions
from zope.interface import implementer
from pyramid.viewderivers import INGRESS
from pyramid.interfaces import ISession, ISessionFactory
import redis
from armonaut.utils import crypto
from armonaut.cache.http import add_vary


def _invalid_method(method):
    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        self._error_message()
    return wrapped


@implementer(ISession)
class InvalidSession(dict):
    def _error_message(self):
        raise RuntimeError('Cannot use request.session in a '
                           'view without uses_session=True')

    __contains__ = _invalid_method(dict.__contains__)
    __delitem__ = _invalid_method(dict.__delitem__)
    __setitem__ = _invalid_method(dict.__setitem__)
    __getitem__ = _invalid_method(dict.__getitem__)
    __iter__ = _invalid_method(dict.__iter__)
    __len__ = _invalid_method(dict.__len__)
    clear = _invalid_method(dict.clear)
    copy = _invalid_method(dict.copy)
    fromkeys = _invalid_method(dict.fromkeys)
    get = _invalid_method(dict.get)
    items = _invalid_method(dict.items)
    keys = _invalid_method(dict.keys)
    pop = _invalid_method(dict.pop)
    popitem = _invalid_method(dict.popitem)
    setdefault = _invalid_method(dict.setdefault)
    update = _invalid_method(dict.update)
    values = _invalid_method(dict.values)

    def invalidate(self):
        self._error_message()

    def flash(self, *args, **kwrgs):
        self._error_message()

    def peek_flash(self, queue=''):
        self._error_message()

    def pop_flash(self, queue=''):
        self._error_message()

    def changed(self):
        self._error_message()

    def get_csrf_token(self):
        self._error_message()

    def new_csrf_token(self):
        self._error_message()

    def should_save(self):
        self._error_message()

    @property
    def sid(self):
        self._error_message()

    @property
    def created(self):
        self._error_message()

    @property
    def new(self):
        self._error_message()


def _changed_method(method):
    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        self.changed()
        return method(self, *args, **kwargs)
    return wrapped


@implementer(ISession)
class Session(dict):

    _csrf_token_key = '_csrf_token'
    _flash_key = '_flash_messages'

    __delitem__ = _changed_method(dict.__delitem__)
    clear = _changed_method(dict.clear)
    pop = _changed_method(dict.pop)
    popitem = _changed_method(dict.popitem)
    update = _changed_method(dict.update)

    def setdefault(self, k, default=None):
        changed = k not in self
        ret = dict.setdefault(self, k, default)
        if changed:
            self.changed()
        return ret

    def __setitem__(self, key, value):
        # Don't mark the session as modified if the value doesn't change.
        if key in self and self[key] == value:
            return
        dict.__setitem__(self, key, value)
        self.changed()

    def __init__(self, data=None, session_id=None, new=True):
        if data is None:
            data = {}
        super().__init__(data)

        self._sid = session_id
        self._changed = False
        self.new = new
        self.created = int(time.time())
        self.invalidated = set()

    @property
    def sid(self):
        if self._sid is None:
            self._sid = crypto.random_token()
        return self._sid

    def changed(self):
        self._changed = True

    def invalidate(self):
        self.clear()
        self.new = True
        self.created = int(time.time())
        self._changed = False

        if self._sid is not None:
            self.invalidated.add(self._sid)
            self._sid = None

    def should_save(self):
        return self._changed

    def _get_flash_queue_key(self, queue):
        return '.'.join(filter(None, [self._flash_key, queue]))

    def flash(self, msg, queue='', allow_duplicate=True):
        queue_key = self._get_flash_queue_key(queue)
        if not allow_duplicate and msg in self.get(queue_key, []):
            return
        self.setdefault(queue_key, []).append(msg)

    def peek_flash(self, queue=''):
        return self.get(self._get_flash_queue_key(queue), [])

    def pop_flash(self, queue=''):
        queue_key = self._get_flash_queue_key(queue)
        messages = self.get(queue_key, [])
        self.pop(queue_key, None)
        return messages

    def new_csrf_token(self):
        self[self._csrf_token_key] = crypto.random_token()
        return self[self._csrf_token_key]

    def get_csrf_token(self):
        token = self.get(self._csrf_token_key)
        if token is None:
            token = self.new_csrf_token()
        return token


@implementer(ISessionFactory)
class RedisSessionFactory:
    cookie_name = 'session'
    max_age = 12 * 60 * 60

    def __init__(self, secret, url):
        self.redis = redis.StrictRedis.from_url(url)
        self.signer = crypto.TimestampSigner(secret, salt='session')

    def __call__(self, request):
        return self._process_request(request)

    @staticmethod
    def _redis_key(session_id):
        return f'armonaut/session/{session_id}'

    def _process_request(self, request):
        request.add_response_callback(self._process_response)

        session_id = request.cookies.get(self.cookie_name)

        # The request didn't claim to have a session
        # so we'll make a new empty session.
        if session_id is None:
            return Session()

        # Check to make sure we have a valid session id
        # and return a fresh session if the session_id
        # is expired or tampered with.
        try:
            session_id = self.signer.unsign(session_id, max_age=self.max_age)
            session_id = session_id.decode('utf-8')
        except crypto.BadSignature:
            return Session()

        # Grab the packed session data from redis
        data = self.redis.get(self._redis_key(session_id))

        # If the session didn't exist in redis give the user
        # a new session.
        if data is None:
            return Session()

        # Unpack the session data into objects and values
        try:
            data = msgpack.unpackb(data, encoding='utf-8', use_list=True)
        # If the session data is invalid give the user a new session
        except (msgpack.exceptions.UnpackException,
                msgpack.exceptions.ExtraData):
            return Session()

        # We were able to load an existing sessions data
        return Session(data, session_id, False)

    def _process_response(self, request, response):
        if isinstance(request.session, InvalidSession):
            return

        # If our session has been invalidated we need to clean
        # up old sessions and potentially delete the cookie
        if request.session.invalidated:
            # Delete all old session ids
            for invalid_id in request.session.invalidated:
                self.redis.delete(self._redis_key(invalid_id))

            # If no new session was created after an invalidate
            # then don't send a cookie with a session.
            if not request.session.should_save():
                response.delete_cookie(self.cookie_name)

        # If the session has been modified we need to save
        # the session to redis and the cookie with newly
        # signed values.
        if request.session.should_save():
            # Use SETEX to allow the value to expire after `max_age` seconds.
            self.redis.setex(
                self._redis_key(request.session.sid),
                self.max_age,
                msgpack.packb(
                    request.session,
                    encoding='utf-8',
                    use_bin_type=True
                )
            )

            # Set the cookie to be the session id and also
            # set MaxAge, HttpOnly, and Secure
            response.set_cookie(
                self.cookie_name,
                self.signer.sign(request.session.sid.encode('utf-8')),
                max_age=self.max_age,
                httponly=True,
                secure=request.scheme == 'https'
            )


def session_view(view, info):
    if info.options.get('uses_session'):
        # If the view allows sessions we'll return the original view
        # with a small wrapper that adds a `Vary: Cookie` header.
        return add_vary('Cookie')(view)
    elif info.exception_only:
        return view
    else:
        # If sessions aren't allowed then we'll wrap the view
        # that ensures that the session is an `InvalidSession`.
        @functools.wraps(view)
        def wrapped(context, request):
            # Store the original session so it can be restored.
            original_session = request.session
            request.session = InvalidSession()

            try:
                return view(context, request)
            finally:
                # Restore the previous session so that
                # the debug toolbar can use it.
                request.session = original_session

        return wrapped


session_view.options = {'uses_session'}


def includeme(config):
    config.set_session_factory(
        RedisSessionFactory(
            config.registry.settings['sessions.secret'],
            config.registry.settings['sessions.url']
        )
    )
    config.add_view_deriver(
        session_view,
        over='csrf_view',
        under=INGRESS
    )
