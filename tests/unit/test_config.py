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
import pretend
from armonaut.config import Configurator, configure


def test_config_returns_configurator(app_config):
    assert isinstance(app_config, Configurator)


def test_configurator_middlewares():
    new_app = pretend.stub()
    middleware = pretend.call_recorder(lambda *args, **kwargs: new_app)

    configurator = Configurator()
    configurator.add_wsgi_middleware(middleware, 1, key='2')

    app = configurator.make_wsgi_app()

    assert app is new_app
    assert len(middleware.calls) == 1


def test_maybe_set_from_os_environ(monkeypatch):
    env = os.environ.copy()
    env['ARMONAUT_SECRET'] = 'value'
    env['REDIS_URL'] = 'url'
    monkeypatch.setattr(os, 'environ', env)

    config = configure()

    assert config.registry.settings['armonaut.secret'] == 'value'
