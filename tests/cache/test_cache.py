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
from armonaut.cache.http import add_vary


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
