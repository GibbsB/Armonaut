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

import enum
import os
import typing
import transaction
from pyramid.config import Configurator as _Configurator
from pyramid.security import Allow
from pyramid.tweens import EXCVIEW


class Environment(enum.Enum):
    PRODUCTION = 'production'
    DEVELOPMENT = 'development'


class Configurator(_Configurator):
    def add_wsgi_middleware(self, middleware, *args, **kwargs):
        middlewares = self.get_settings().setdefault('wsgi.middlewares', [])
        middlewares.append((middleware, args, kwargs))

    def make_wsgi_app(self, *args, **kwargs):
        app = super().make_wsgi_app(*args, **kwargs)
        for middleware, args, kw in self.get_settings().get('wsgi.middlewares', []):
            app = middleware(app, *args, **kw)
        return app


class RootFactory(object):
    __parent__ = None
    __name__ = None

    __acl__ = [
        (Allow, 'group:admins', 'admin')
    ]

    def __init__(self, request):
        pass


def maybe_set(settings: typing.Dict[str, typing.Any],
              name: str,
              env: str,
              coercer: typing.Optional[typing.Callable[[str], typing.Any]]=None,
              default: typing.Any=None):

    value = os.environ.get(env)
    if value is not None:
        if coercer is not None:
            value = coercer(value)
        settings.setdefault(name, value)
    elif default is not None:
        settings.setdefault(name, default)


def _tm_activate_hook(request) -> bool:
    # Don't activate our transaction manager on the debug toolbar
    # or on static resources
    if request.path.startswith(('/_debug_toolbar', '/static')):
        return False
    return True


def configure(settings=None) -> Configurator:
    if settings is None:
        settings = {}

    # Gather all settings from the environment
    maybe_set(settings, 'armonaut.env', 'ARMONAUT_ENV',
              coercer=lambda x: Environment(x.lower()),
              default=Environment.PRODUCTION)
    maybe_set(settings, 'armonaut.secret', 'ARMONAUT_SECRET')

    maybe_set(settings, 'sessions.url', 'REDIS_URL')
    maybe_set(settings, 'sessions.secret', 'ARMONAUT_SECRET')

    # Setup our development environment
    if settings['armonaut.env'] == Environment.DEVELOPMENT:
        settings.setdefault('pyramid.reload_assets', True)
        settings.setdefault('pyramid.reload_templates', True)
        settings.setdefault('pyramid.prevent_http_cache', True)
        settings.setdefault('debugtoolbar.hosts', ['0.0.0.0/0'])
        settings.setdefault('logging.level', 'DEBUG')
        settings.setdefault(
            'debugtoolbar.panels',
            [f'pyramid_debugtoolbar.panels.{panel}'
                for panel in [
                    'versions.VersionDebugPanel',
                    'settings.SettingsDebugPanel',
                    'headers.HeaderDebugPanel',
                    'request_vars.RequestVarsDebugPanel',
                    'renderings.RenderingsDebugPanel',
                    'logger.LoggingPanel',
                    'performance.PerformanceDebugPanel',
                    'routes.RoutesDebugPanel',
                    'sqla.SQLADebugPanel',
                    'tweens.TweensDebugPanel',
                    'introspection.IntrospectionDebugPanel'
                ]
             ]
        )

    # Create a configuration from the settings
    config = Configurator(settings=settings)
    config.set_root_factory(RootFactory)

    # Add the Pyramid debugtoolbar for development debugging
    if config.registry.settings['armonaut.env'] == Environment.DEVELOPMENT:
        config.include('pyramid_debugtoolbar')

    # Configure Jinja2 as our template renderer
    config.include('pyramid_jinja2')
    config.add_settings({'jinja2.newstyle': True})

    for jinja2_renderer in ['.html']:
        config.add_jinja2_renderer(jinja2_renderer)
        config.add_jinja2_search_path('armonaut:templates', name=jinja2_renderer)

    # Setup our transaction manager before the database
    config.include('pyramid_retry')
    config.add_settings({
        'tm.attempts': 3,
        'tm.manager_hook': lambda request: transaction.TransactionManager(),
        'tm.activate_hook': _tm_activate_hook,
        'tm.annotate_user': False
    })
    config.include('pyramid_tm')

    # Register support for services
    config.include('pyramid_services')

    # Register support for sessions
    config.include('.sessions')

    # Register HTTP compression
    config.add_tween(
        'armonaut.utils.compression.compression_tween_factory',
        over=[
            'pyramid_debugtoolbar.toolbar_tween_factory',
            EXCVIEW
        ]
    )

    # Scan everything for additional configuration
    config.scan(ignore=[
        'armonaut.wsgi',
        'armonaut.routes'
    ])
    config.include('.routes')
    config.commit()

    return config
