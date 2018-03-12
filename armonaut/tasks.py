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
import celery
import pyramid.scripting
import pyramid_retry
import transaction
import venusian
from pyramid.threadlocal import get_current_request


class Task(celery.Task):
    def __new__(cls, *args, **kwargs):
        obj = super().__new__(cls, *args, **kwargs)
        if getattr(obj, '__header__', None) is not None:
            obj.__header__ = functools.partial(obj.__header__, object())

        @functools.wraps(obj.run)
        def run(*args, **kwargs):
            original_run = obj._wh_original_run
            request = obj.get_request()

            with request.tm:
                try:
                    return original_run(*args, **kwargs)
                except BaseException as exc:
                    if (isinstance(exc, pyramid_retry.RetryableException) or
                            pyramid_retry.IRetryableError.providedBy(exc)):
                        raise obj.retry(exc=exc)
                    raise

        obj._wh_original_run, obj.run = obj.run, run
        return obj

    def __call__(self, *args, **kwargs):
        return super().__call__(*(self.get_request(),) + args, **kwargs)

    def get_request(self):
        if not hasattr(self.request, 'pyramid_env'):
            registry = self.app.pyramid_config.registry
            env = pyramid.scripting.prepare(registry=registry)
            env['request'].tm = transaction.TransactionManager(explicit=True)
            self.request.update(pyramid_env=env)

        return self.request.pyramid_env['request']

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        if hasattr(self.request, 'pyramid_env'):
            pyramid_env = self.request.pyramid_env
            pyramid_env['request']._process_finished_callbacks()
            pyramid_env['closer']()

    def apply_async(self, *args, **kwargs):
        request = get_current_request()

        if request is None or not hasattr(request, 'tm'):
            return super().apply_async(*args, **kwargs)

        request.tm.get().addAfterCommitHook(
            self._after_commit_hook,
            args=args,
            kwargs=kwargs
        )

    def _after_commit_hook(self, success, *args, **kwargs):
        if success:
            super().apply_async(*args, **kwargs)


def task(**kwargs):
    kwargs.setdefault('shared', False)

    def deco(wrapped):
        def callback(scanner, name, wrapped):
            celery_app = scanner.config.registry['celery.app']
            celery_app.task(**kwargs)(wrapped)

        venusian.attach(wrapped, callback)
        return wrapped
    return deco


def _get_task(celery_app, task_func):
    task_name = celery_app.gen_task_name(
        task_func.__name__,
        task_func.__module__,
    )
    return celery_app.tasks[task_name]


def _get_task_from_request(request):
    celery_app = request.registry['celery.app']
    return functools.partial(_get_task, celery_app)


def _get_task_from_config(config, task):
    celery_app = config.registry['celery.app']
    return _get_task(celery_app, task)


def _get_celery_app(config):
    return config.registry['celery.app']


def _add_periodic_task(config, schedule, func, args=(), kwargs=(), name=None, **opts):
    def add_task():
        config.registry['celery.app'].add_periodic_task(
            schedule,
            config.task(func).s(),
            args=args,
            kwargs=kwargs,
            name=name,
            **opts
        )
    config.action(None, add_task, order=100)


def includeme(config):
    settings = config.registry.settings

    config.registry['celery.app'] = celery.Celery(
        'armonaut',
        autofinalize=False,
        set_as_current=False
    )
    config.registry['celery.app'].conf.update(
        accept_content=['msgpack', 'json'],
        broker_url=settings['celery.broker_url'],
        result_backend=settings['celery.result_url'],
        result_compression='gzip',
        result_serializer='json',
        task_queue_ha_policy='all',
        task_serializer='json',
        worker_disable_rate_limits=True,
        REDBEAT_REDIS_URL=settings['celery.scheduler_url']
    )

    config.registry['celery.app'].Task = Task
    config.registry['celery.app'].pyramid_config = config

    config.action(
        ('celery', 'finalize'),
        config.registry['celery.app'].finalize
    )

    config.add_directive(
        'add_periodic_task',
        _add_periodic_task,
        action_wrap=False
    )

    config.add_directive('make_celery_app', _get_celery_app, action_wrap=False)
    config.add_directive('task', _get_task_from_config, action_wrap=False)
    config.add_request_method(_get_task_from_request, name='task', reify=True)