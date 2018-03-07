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

__all__ = ['add_vary']


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
