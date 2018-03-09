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

import pretend
from armonaut.sessions import RedisSessionFactory
from ..common import requires_external_services


@requires_external_services
def test_session_added_and_getting_from_redis(app_config, pyramid_request):
    factory = RedisSessionFactory(
        app_config.registry.settings['sessions.secret'],
        app_config.registry.settings['sessions.url']
    )

    request = pyramid_request
    request.scheme = 'https'

    session1 = factory(request)
    request.session = session1

    session1['a'] = 1
    response = pretend.stub(set_cookie=pretend.call_recorder(lambda *args, **kwargs: None))

    factory._process_response(request, response)

    assert len(response.set_cookie.calls) == 1
    call = response.set_cookie.calls[0]
    name, value = call.args
    request.cookies = {name: value}

    session2 = factory(request)
    assert session2['a'] == 1
