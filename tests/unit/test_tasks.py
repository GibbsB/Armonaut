# Copyright 2018 Seth Michael Larson
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mock
import pretend
import pytest
import transaction
from celery import Celery
from pyramid import scripting
from pyramid_retry import RetryableException
from armonaut import tasks


def test_header():
    def header(request, thing):
        pass

    task_type = type(
        'Foo',
        (tasks.Task,),
        {'__header__': staticmethod(header)}
    )

    obj = task_type()
    obj.__header__(object())


def test_call(monkeypatch):
    request = pretend.stub()
    registry = pretend.stub()
    result = pretend.stub()

    prepared = {
        'registry': registry,
        'request': request,
        'closer': pretend.call_recorder(lambda: None)
    }
    prepare = pretend.call_recorder(lambda *a, **kw: prepared)
    monkeypatch.setattr(scripting, 'prepare', prepare)

    @pretend.call_recorder
    def runner(irequest):
        assert irequest is request
        return result

    task = tasks.Task()
    task.app = Celery()
    task.app.pyramid_config = pretend.stub(registry=registry)
    task.run = runner

    assert task() is result
    assert prepare.calls == [pretend.call(registry=registry)]
    assert runner.calls == [pretend.call(request)]


def test_without_request(monkeypatch):
    async_result = pretend.stub()
    super_class = pretend.stub(
        apply_async=pretend.call_recorder(lambda *a, **kw: async_result)
    )
    real_super = __builtins__['super']
    inner_super = pretend.call_recorder(lambda *a, **kw: super_class)

    def fake_super(*args, **kwargs):
        if not args and not kwargs:
            return inner_super(*args, **kwargs)
        else:
            return real_super(*args, **kwargs)

    get_current_request = pretend.call_recorder(lambda: None)
    monkeypatch.setattr(tasks, 'get_current_request', get_current_request)

    task = tasks.Task()
    task.app = Celery()

    monkeypatch.setitem(__builtins__, 'super', fake_super)

    assert task.apply_async() is async_result
    assert super_class.apply_async.calls == [pretend.call()]
    assert get_current_request.calls == [pretend.call()]
    assert inner_super.calls == [pretend.call()]


def test_request_after_commit(monkeypatch):
    manager = pretend.stub(
        addAfterCommitHook=pretend.call_recorder(lambda *a, **kw: None)
    )
    request = pretend.stub(
        tm=pretend.stub(get=pretend.call_recorder(lambda: manager))
    )
    get_current_request = pretend.call_recorder(lambda: request)
    monkeypatch.setattr(tasks, 'get_current_request', get_current_request)

    task = tasks.Task()
    task.app = Celery()

    args = (pretend.stub(), pretend.stub())
    kwargs = {'foo': pretend.stub()}

    assert task.apply_async(*args, **kwargs) is None
    assert get_current_request.calls == [pretend.call()]
    assert request.tm.get.calls == [pretend.call()]
    assert manager.addAfterCommitHook.calls == [
        pretend.call(task._after_commit_hook, args=args, kwargs=kwargs)
    ]


@pytest.mark.parametrize('success', [True, False])
def test_after_commit_hook(monkeypatch, success):
    args = [pretend.stub(), pretend.stub()]
    kwargs = {'foo': pretend.stub(), 'bar': pretend.stub()}

    super_class = pretend.stub(
        apply_async=pretend.call_recorder(lambda *a, **kw: None)
    )
    real_super = __builtins__['super']
    inner_super = pretend.call_recorder(lambda *a, **kw: super_class)

    def fake_super(*args, **kwargs):
        if not args and not kwargs:
            return inner_super(*args, **kwargs)
        else:
            return real_super(*args, **kwargs)

    get_current_request = pretend.call_recorder(lambda: None)
    monkeypatch.setattr(tasks, 'get_current_request', get_current_request)

    task = tasks.Task()
    task.app = Celery()

    monkeypatch.setitem(__builtins__, 'super', fake_super)

    task._after_commit_hook(success, *args, **kwargs)

    if success:
        assert inner_super.calls == [pretend.call()]
    else:
        assert inner_super.calls == []


def test_creates_request(monkeypatch):
    registry = pretend.stub()
    pyramid_env = {'request': pretend.stub()}

    monkeypatch.setattr(scripting, 'prepare', lambda *a, **k: pyramid_env)

    obj = tasks.Task()
    obj.app.pyramid_config = pretend.stub(registry=registry)

    request = obj.get_request()

    assert obj.request.pyramid_env == pyramid_env
    assert request is pyramid_env['request']
    assert isinstance(request.tm, transaction.TransactionManager)


def test_reuses_request():
    pyramid_env = {'request': pretend.stub()}

    obj = tasks.Task()
    obj.request.update(pyramid_env=pyramid_env)

    assert obj.get_request() is pyramid_env['request']


def test_run_creates_transaction():
    result = pretend.stub()
    args = pretend.stub()
    kwargs = pretend.stub()

    request = pretend.stub(
        tm=pretend.stub(
            __enter__=pretend.call_recorder(lambda *a, **kw: None),
            __exit__=pretend.call_recorder(lambda *a, **kw: None)
        )
    )

    @pretend.call_recorder
    def run(arg_, *, kwarg_=None):
        assert arg_ is args
        assert kwarg_ is kwargs
        return result

    task_type = type(
        'Foo',
        (tasks.Task,),
        {'run': staticmethod(run)}
    )

    obj = task_type()
    obj.get_request = lambda: request

    assert obj.run(args, kwarg_=kwargs) is result
    assert run.calls == [pretend.call(args, kwarg_=kwargs)]
    assert request.tm.__enter__.calls == [pretend.call()]
    assert request.tm.__exit__.calls == [pretend.call(None, None, None)]


def test_run_retries_failed_transaction():
    class RetryThisException(RetryableException):
        pass

    class Retry(Exception):
        pass

    def run():
        raise RetryThisException

    task_type = type(
        'Foo',
        (tasks.Task,),
        {'run': staticmethod(run), 'retry': lambda *a, **kw: Retry()}
    )

    request = pretend.stub(
        tm=pretend.stub(
            __enter__=pretend.call_recorder(lambda *a, **kw: None),
            __exit__=pretend.call_recorder(lambda *a, **kw: None)
        )
    )

    obj = task_type()
    obj.get_request = lambda: request

    with pytest.raises(Retry):
        obj.run()

    assert request.tm.__enter__.calls == [pretend.call()]
    assert request.tm.__exit__.calls == [pretend.call(Retry, mock.ANY, mock.ANY)]


def test_run_non_retryable_exception():
    def run():
        raise ValueError

    task_type = type(
        'Foo',
        (tasks.Task,),
        {'run': staticmethod(run)}
    )

    request = pretend.stub(
        tm=pretend.stub(
            __enter__=pretend.call_recorder(lambda *a, **kw: None),
            __exit__=pretend.call_recorder(lambda *a, **kw: None)
        )
    )

    obj = task_type()
    obj.get_request = lambda: request

    with pytest.raises(ValueError):
        obj.run()

    assert request.tm.__enter__.calls == [pretend.call()]
    assert request.tm.__exit__.calls == [pretend.call(ValueError, mock.ANY, mock.ANY)]


def test_after_return_without_pyramid_env():
    obj = tasks.Task()
    assert obj.after_return(
        pretend.stub(),
        pretend.stub(),
        pretend.stub(),
        pretend.stub(),
        pretend.stub(),
        pretend.stub()
    ) is None


def test_after_return_closes_env_runs_request_callbacks():
    obj = tasks.Task()
    obj.request.pyramid_env = {
        'request': pretend.stub(
            _process_finished_callbacks=pretend.call_recorder(
                lambda: None
            )
        ),
        'closer': pretend.call_recorder(lambda: None)
    }

    obj.after_return(
        pretend.stub(),
        pretend.stub(),
        pretend.stub(),
        pretend.stub(),
        pretend.stub(),
        pretend.stub()
    )

    assert obj.request.pyramid_env['request']._process_finished_callbacks.calls == [pretend.call()]
    assert obj.request.pyramid_env['closer'].calls == [pretend.call()]


def test_get_task():
    task_func = pretend.stub(__name__='task_func', __module__='tests.foo')
    task_obj = pretend.stub()
    celery_app = pretend.stub(
        gen_task_name=lambda func, module: f'{module}.{func}',
        tasks={'tests.foo.task_func': task_obj}
    )
    assert tasks._get_task(celery_app, task_func) is task_obj


def test_get_task_via_request():
    task_func = pretend.stub(__name__='task_func', __module__='tests.foo')
    task_obj = pretend.stub()
    celery_app = pretend.stub(
        gen_task_name=lambda func, module: module + '.' + func,
        tasks={'tests.foo.task_func': task_obj},
    )

    request = pretend.stub(registry={'celery.app': celery_app})
    get_task = tasks._get_task_from_request(request)

    assert get_task(task_func) is task_obj


def test_get_task_via_config():
    task_func = pretend.stub(__name__='task_func', __module__='tests.foo')
    task_obj = pretend.stub()
    celery_app = pretend.stub(
        gen_task_name=lambda func, module: module + '.' + func,
        tasks={'tests.foo.task_func': task_obj},
    )

    config = pretend.stub(registry={'celery.app': celery_app})

    assert tasks._get_task_from_config(config, task_func)


def test_add_periodic_task():
    signature = pretend.stub()
    task_obj = pretend.stub(s=lambda: signature)
    celery_app = pretend.stub(
        add_periodic_task=pretend.call_recorder(lambda *a, **k: None),
    )
    actions = []
    config = pretend.stub(
        action=pretend.call_recorder(lambda d, f, order: actions.append(f)),
        registry={'celery.app': celery_app},
        task=pretend.call_recorder(lambda t: task_obj),
    )

    schedule = pretend.stub()
    func = pretend.stub()

    tasks._add_periodic_task(config, schedule, func)

    for action in actions:
        action()

    assert config.action.calls == [pretend.call(None, mock.ANY, order=100)]
    assert config.task.calls == [pretend.call(func)]
    assert celery_app.add_periodic_task.calls == [
        pretend.call(schedule, signature, args=(), kwargs=(), name=None),
    ]


def test_make_celery_app():
    celery_app = pretend.stub()
    config = pretend.stub(registry={'celery.app': celery_app})

    assert tasks._get_celery_app(config) is celery_app


def test_includeme():
    registry_dict = {}
    config = pretend.stub(
        action=pretend.call_recorder(lambda *a, **kw: None),
        add_directive=pretend.call_recorder(lambda *a, **kw: None),
        add_request_method=pretend.call_recorder(lambda *a, **kw: None),
        registry=pretend.stub(
            __getitem__=registry_dict.__getitem__,
            __setitem__=registry_dict.__setitem__,
            settings={
                'celery.broker_url': pretend.stub(),
                'celery.result_url': pretend.stub(),
                'celery.scheduler_url': pretend.stub(),
            },
        ),
    )
    tasks.includeme(config)

    app = config.registry['celery.app']

    assert app.Task is tasks.Task
    assert app.pyramid_config is config
    for key, value in {
            'broker_url': config.registry.settings['celery.broker_url'],
            'worker_disable_rate_limits': True,
            'result_backend': config.registry.settings['celery.result_url'],
            'result_serializer': 'json',
            'task_serializer': 'json',
            'accept_content': ['msgpack', 'json'],
            'result_compression': 'gzip',
            'task_queue_ha_policy': 'all',
            'REDBEAT_REDIS_URL': (
                config.registry.settings['celery.scheduler_url'])}.items():
        assert app.conf[key] == value
    assert config.action.calls == [
        pretend.call(('celery', 'finalize'), app.finalize),
    ]
    assert config.add_directive.calls == [
        pretend.call(
            'add_periodic_task',
            tasks._add_periodic_task,
            action_wrap=False,
        ),
        pretend.call(
            'make_celery_app',
            tasks._get_celery_app,
            action_wrap=False,
        ),
        pretend.call('task', tasks._get_task_from_config, action_wrap=False),
    ]
    assert config.add_request_method.calls == [
        pretend.call(tasks._get_task_from_request, name='task', reify=True),
    ]
