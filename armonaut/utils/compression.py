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

import base64
import hashlib
from collections.abc import Sequence

ENCODINGS = ['identity', 'br', 'gzip']
DEFAULT_ENCODING = 'identity'
BUFFER_MAX = 1 * 1024 * 1024


def _compressor(request, response):
    # Skip items with a Vary: Cookie/Authorization because we
    # don't know if they're vulnerable to CRIME-esque attacks.
    if (response.vary is not None and
            set(response.vary) & {'Cookie', 'Authorization'}):
        return

    # Avoid compression if there's already an encoding
    if 'Content-Encoding' in response.headers:
        return

    # Ensure that the Accept-Encoding header gets added to the response.
    vary = set(response.vary if response.vary is not None else [])
    vary.add('Accept-Encoding')
    response.vary = vary

    # Determine the correct encoding from our request.
    target_encoding = request.accept_encoding.best_match(
        ENCODINGS,
        default_match=DEFAULT_ENCODING
    )

    # If we have a Sequence instead of an iterable we'll
    # assume the response isn't streaming.
    streaming = not isinstance(response.app_iter, Sequence)

    # If we're streaming and we're given a suitable content length
    # then we'll convert it to a non-streaming response.
    if (streaming and response.content_length is not None and
            response.content_length < BUFFER_MAX):
        _ = response.body  # noqa: Accessing response.body here to collapse app_iter
        streaming = False

    if streaming:
        # If we're streaming we need to lazily encode the content.
        response.encode_content(encoding=target_encoding, lazy=True)

        # We no longer know the Content-Length of the response due to encoding.
        response.content_length = None

        # If an ETag header is already calculated we need to create a new one
        # based on the old one so add some data to the old ETag and rehash it.
        if response.etag is not None:
            md5_digest = hashlib.md5((response.etag + ';gzip').encode('utf-8'))
            md5_digest = base64.b64encode(md5_digest.digest()).replace(b'\n', b'').decode('utf-8')
            response.etag = md5_digest.rstrip('=')

    else:
        original_length = len(response.body)
        response.encode_content(encoding=target_encoding, lazy=False)

        # If encoding the content is actually longer now we should revert.
        if original_length < len(response.body):
            response.decode_content()

        # If we've added an encoding we should recompute the ETag
        if response.content_encoding is not None:
            response.md5_etag()


def compression_tween_factory(handler, registry):
    def compression_tween(request):
        response = handler(request)

        # We use a response callback so compression is applied last
        # after all of the other callbacks and tweens are called.
        request.add_response_callback(_compressor)
        return response
    return compression_tween
