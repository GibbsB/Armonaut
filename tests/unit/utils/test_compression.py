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
from pyramid.response import Response
from webob.acceptparse import Accept, NoAccept
from webob.response import gzip_app_iter
from armonaut.utils.compression import (
    _compressor as compressor,
    compression_tween_factory
)


@pytest.mark.parametrize('vary', [['Cookie'], ['Authorization'], ['Cookie', 'Authorization']])
def test_compression_stops_on_vary(vary):
    request = pretend.stub()
    response = pretend.stub(vary=vary)

    compressor(request, response)


def test_compression_stops_if_content_encoded():
    request = pretend.stub()
    response = pretend.stub(
        headers={'Content-Encoding': 'anything'},
        vary=None
    )

    compressor(request, response)


@pytest.mark.parametrize(
    ['vary', 'expected'],
    [
        (None, {'Accept-Encoding'}),
        (['Another-Header'], {'Accept-Encoding', 'Another-Header'})
    ]
)
def test_sets_vary_accept_encoding(vary, expected):
    request = pretend.stub(accept_encoding=NoAccept())
    response = Response(body=b'foo')
    response.vary = vary

    compressor(request, response)

    assert set(response.vary) == expected


def test_compresses_non_streaming():
    body = b'x' * 100
    compressed = b''.join(list(gzip_app_iter([body])))

    request = pretend.stub(accept_encoding=Accept('gzip'))
    response = Response(body=body)
    response.md5_etag()

    original_etag = response.etag

    compressor(request, response)

    assert response.content_encoding == 'gzip'
    assert response.content_length == len(compressed)
    assert response.body == compressed
    assert response.etag != original_etag


def test_compresses_streaming():
    body = b'x' * 100
    compressed = b''.join(list(gzip_app_iter([body])))

    request = pretend.stub(accept_encoding=Accept('gzip'))
    response = Response(app_iter=iter([body]))

    compressor(request, response)

    assert response.content_encoding == 'gzip'
    assert response.content_length is None
    assert response.body == compressed


def test_compresses_streaming_with_etag():
    body = b'x' * 100
    compressed = b''.join(list(gzip_app_iter([body])))

    request = pretend.stub(accept_encoding=Accept('gzip'))
    response = Response(app_iter=iter([body]))
    response.etag = 'foo'

    compressor(request, response)

    assert response.content_encoding == "gzip"
    assert response.content_length is None
    assert response.body == compressed
    assert response.etag == 'rfbezwKUdGjz6VPWDLDTvA'


def test_buffers_small_streaming():
    body = b'x' * 100
    compressed = b''.join(list(gzip_app_iter([body])))

    request = pretend.stub(accept_encoding=Accept('gzip'))
    response = Response(app_iter=iter([body]),
                        content_length=len(body))

    compressor(request, response)

    assert response.content_encoding == 'gzip'
    assert response.content_length == len(compressed)
    assert response.body == compressed


def test_does_not_compress_small_bodies():
    body = b'foo'

    request = pretend.stub(accept_encoding=Accept('gzip'))
    response = Response(body=body)

    compressor(request, response)

    assert response.content_encoding is None
    assert response.content_length == len(body)
    assert response.body == body


def test_compression_tween_factory():
    registry = pretend.stub()
    request = pretend.stub(add_response_callback=pretend.call_recorder(lambda *args, **kwargs: None))
    response = pretend.stub()

    def handler(inner_request):
        assert inner_request is request
        return response

    tween = compression_tween_factory(handler, registry)

    assert tween(request) is response
    assert request.add_response_callback.calls == [pretend.call(compressor)]
