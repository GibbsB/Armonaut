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

import os
import pytest
import webtest as _webtest
import pyramid.testing
from armonaut.config import configure, Environment


@pytest.fixture
def app_config():
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    config = configure({
        'armonaut.env': Environment.DEVELOPMENT,
        'armonaut.secret': 'notasecret',
        'sessions.secret': 'notasecret',
        'sessions.url': redis_url
    })
    return config


@pytest.fixture
def pyramid_request():
    request = pyramid.testing.DummyRequest()
    return request


@pytest.yield_fixture()
def webtest(app_config):
    return _webtest.TestApp(app_config.make_wsgi_app())
