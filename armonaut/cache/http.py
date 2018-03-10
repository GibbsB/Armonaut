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

import collections.abc
import functools

__all__ = ['add_vary']

BUFFER_MAX = 1024 * 1024


def add_vary_callback(*varies):
    def wrapped(request, response):
        vary = set(response.vary if response.vary is not None else [])
        vary |= set(varies)
        response.vary = vary
    return wrapped


def add_vary(*varies):
    def wrapper(view):
        @functools.wraps(view)
        def wrapped(context, request):
            request.add_response_callback(add_vary_callback(*varies))
            return view(context, request)
        return wrapped
    return wrapper


def conditional_http_tween_factory(handler, registry):
    def conditional_http_tween(request):
        response = handler(request)

        # If the Last-Modified header has been set enable
        # conditional response handling.
        if response.last_modified is not None:
            response.conditional_response = True

        # Only enable conditional response handling for ETag if
        # we're given an ETag or we have a buffered response and
        # can generate the ETag header ourselves.
        if response.etag is not None:
            response.conditional_response = True

        elif response.status_code == 200 and request.method in {'GET', 'HEAD'}:
            # If we're streaming a response and it's small enough we
            # can buffer it in memory and generate an ETag.
            streaming = not isinstance(response.app_iter, collections.abc.Sequence)
            if (streaming and response.content_length is not None and
                    response.content_length <= BUFFER_MAX):
                _ = response.body  # noqa
                streaming = False

            # If we're not streaming the response still we can generate an ETag.
            if not streaming:
                response.conditional_response = True
                response.md5_etag()

        return response
    return conditional_http_tween


def includeme(config):
    config.add_tween('armonaut.cache.http.conditional_http_tween_factory')
