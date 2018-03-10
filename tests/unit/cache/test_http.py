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
import pretend
from armonaut.cache.http import (
    add_vary, includeme, conditional_http_tween_factory
)


@pytest.mark.parametrize(
    'vary',
    [None,
     [],
     ['bar'],
     ['foo', 'bar'],
     ['foobar']]
)
def test_add_vary(vary):
    """Assert that the add_vary() directive correctly adds
    a non-duplicate value to the Vary HTTP header."""
    class FakeRequest:
        def __init__(self):
            self.callbacks = []

        def add_response_callback(self, callback):
            self.callbacks.append(callback)

    request = FakeRequest()
    context = pretend.stub()
    response = pretend.stub(vary=vary)

    def view(context, request):
        return response

    assert add_vary('foobar')(view)(context, request) is response
    assert len(request.callbacks) == 1

    request.callbacks[0](request, response)

    if vary is None:
        vary = []

    assert response.vary == {'foobar'} | set(vary)


def test_has_last_modified():
    response = pretend.stub(
        last_modified=pretend.stub(),
        status_code=200,
        etag=None,
        conditional_response=False,
        app_iter=iter([b'data']),
        content_length=None
    )
    handler = pretend.call_recorder(lambda request: response)
    request = pretend.stub(method='GET')

    tween = conditional_http_tween_factory(handler, pretend.stub())

    assert tween(request) is response
    assert handler.calls == [pretend.call(request)]
    assert response.conditional_response


def test_has_etag():
    response = pretend.stub(
        last_modified=None,
        status_code=200,
        etag='abc',
        conditional_response=False,
        app_iter=iter([b'data']),
        content_length=None
    )
    handler = pretend.call_recorder(lambda request: response)
    request = pretend.stub(method='GET')

    tween = conditional_http_tween_factory(handler, pretend.stub())

    assert tween(request) is response
    assert handler.calls == [pretend.call(request)]
    assert response.conditional_response


@pytest.mark.parametrize('method', ['GET', 'HEAD'])
def test_generate_etag(method):
    response = pretend.stub(
        last_modified=None,
        status_code=200,
        etag=None,
        conditional_response=False,
        app_iter=[b'data'],
        content_length=4,
        md5_etag=pretend.call_recorder(lambda: None)
    )
    handler = pretend.call_recorder(lambda request: response)
    request = pretend.stub(method=method)

    tween = conditional_http_tween_factory(handler, pretend.stub())

    assert tween(request) is response
    assert handler.calls == [pretend.call(request)]
    assert response.conditional_response
    assert response.md5_etag.calls == [pretend.call()]


def test_buffered_body():
    response = pretend.stub(
        last_modified=None,
        status_code=200,
        etag=None,
        conditional_response=False,
        app_iter=iter([b'data']),
        content_length=4,
        md5_etag=pretend.call_recorder(lambda: None),
        body=None
    )
    handler = pretend.call_recorder(lambda request: response)
    request = pretend.stub(method='GET')

    tween = conditional_http_tween_factory(handler, pretend.stub())

    assert tween(request) is response
    assert handler.calls == [pretend.call(request)]
    assert response.conditional_response
    assert response.md5_etag.calls == [pretend.call()]


@pytest.mark.parametrize(
    ['method', 'size'],
    [('GET', (1024 * 1024) + 1),
     ('POST', 4)]
)
def test_unbuffered_body(method, size):
    response = pretend.stub(
        last_modified=None,
        status_code=200,
        etag=None,
        conditional_response=False,
        app_iter=iter([b'data']),
        content_length=size,
        md5_etag=pretend.call_recorder(lambda: None),
        body=None
    )
    handler = pretend.call_recorder(lambda request: response)
    request = pretend.stub(method=method)

    tween = conditional_http_tween_factory(handler, pretend.stub())

    assert tween(request) is response
    assert handler.calls == [pretend.call(request)]
    assert not response.conditional_response
    assert response.md5_etag.calls == []


def test_includeme():
    config = pretend.stub(add_tween=pretend.call_recorder(lambda _: None))

    includeme(config)

    assert config.add_tween.calls == [pretend.call('armonaut.cache.http.conditional_http_tween_factory')]
