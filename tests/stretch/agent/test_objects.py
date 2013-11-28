from mock import Mock, patch, DEFAULT, PropertyMock
from nose.tools import raises, assert_raises
from unittest import TestCase

from stretch.agent import objects
from stretch.agent.app import TaskException


def patch_func(func):
    return patch('stretch.agent.objects.resources.PersistentObject.%s'
                 % func, Mock(return_value=None))


class TestTask(TestCase):
    def setUp(self):
        self.task = objects.Task()


class ObjectTestCase(TestCase):
    def apply_patch(self, patch):
        obj = patch.start()
        self.addCleanup(patch.stop)
        return obj


class TestInstance(ObjectTestCase):
    def setUp(self):
        self.config = self.apply_patch(patch(
            'stretch.config_managers.EtcdConfigManager'))
        self.instance_save = self.apply_patch(patch_func('save'))
        self.apply_patch(patch_func('__init__'))
        self.apply_patch(patch('stretch.agent.objects.container_dir', '/var'))

        self.instance = objects.Instance('1')

    @patch_func('create')
    @patch.object(objects.Instance, 'start')
    def test_should_start_when_created(self, start):
        instance = objects.Instance.create({})
        start.assert_called_with()

    @patch_func('delete')
    @patch.object(objects.Instance, 'stop')
    def test_should_stop_when_deleted(self, stop):
        self.instance.delete()
        stop.assert_called_with()

    @raises(TaskException)
    @patch.object(objects.Instance, 'running', new_callable=PropertyMock)
    def test_reload_should_fail_if_running(self, running):
        running.return_value = False

        self.instance.reload()

    @patch('stretch.utils.run_cmd')
    @patch.object(objects.Instance, 'restart')
    @patch.object(objects.Instance, 'running', new_callable=PropertyMock)
    def test_reload(self, running, restart, run_cmd):
        running.return_value = True
        run_cmd.return_value = ('output', 0)
        self.instance.data['cid'] = 'cid'

        self.instance.reload()

        run_cmd.assert_called_with(['lxc-attach', '-n', 'cid', '--',
            '/bin/bash', '/var/files/autoload.sh'], allow_errors=True)
        assert not restart.called

    @patch('stretch.utils.run_cmd')
    @patch.object(objects.Instance, 'restart')
    @patch.object(objects.Instance, 'running', new_callable=PropertyMock)
    def test_should_restart_when_reload_fails(self, running, restart, run_cmd):
        running.return_value = True
        run_cmd.return_value = ('output', 1)
        self.instance.data['cid'] = 'cid'

        self.instance.reload()

        run_cmd.assert_called_with(['lxc-attach', '-n', 'cid', '--',
            '/bin/bash', '/var/files/autoload.sh'], allow_errors=True)
        assert restart.called

    def test_restart(self):
        with patch.multiple(self.instance, stop=DEFAULT, start=DEFAULT) as f:
            self.instance.restart()
            f['stop'].assert_called_with()
            f['start'].assert_called_with()

    @patch.object(objects.Instance, 'running', new_callable=PropertyMock)
    def test_should_only_start_when_ready(self, running):
        running.return_value = False
        self.instance.get_node = Mock(return_value=None)

        with assert_raises(TaskException):
            self.instance.start()

        node = Mock()
        node.pulled = False
        self.instance.get_node.return_value = node

        with assert_raises(TaskException):
            self.instance.start()

    """
    @patch('stretch.utils.run_cmd')
    @patch('stretch.agent.Instance.get_run_args')
    @patch.object(objects.Instance, 'compile_templates')
    @patch.object(objects.Instance, 'running', new_callable=PropertyMock)
    def test_start(self, running, compile_templates, get_run_args, run_cmd):
        running.return_value = True
        node = Mock()
        node.pulled = False
        self.instance.get_node.return_value = node

        self.instance.start()

        compile_templates.assert_called_with(node)

        instance = self.get_instance()
        running.return_value = False
        instance.get_node = Mock()
        node = Mock()
        instance.get_node.return_value = node
        run_cmd.return_value = ('new_cid', 0)
        instance.start()
        self.assertEquals(instance.data['cid'], 'new_cid')
    """

    @patch('stretch.utils.run_cmd')
    @patch.object(objects.Instance, 'config_manager',
        new_callable=PropertyMock)
    def test_stop(self, config_manager, run_cmd):
        config_manager.return_value = cm = Mock()
        self.instance.data['cid'] = 'cid'
        self.instance.data['endpoint'] = 'endpoint'
        self.instance.data['config_key'] = 'config_key'

        self.instance.stop()

        cm.delete.assert_called_with('config_key')
        run_cmd.assert_called_with(['docker', 'stop', 'cid'])
        self.assertEquals(self.instance.data['cid'], None)
        self.assertEquals(self.instance.data['endpoint'], None)
        self.instance_save.assert_called_with()

    def test_running(self):
        self.instance.data['cid'] = None
        assert not self.instance.running
        self.instance.data['cid'] = 'cid'
        assert self.instance.running


class TestLoadBalancer(TestCase):
    def setUp(self):
        pass


class TestNode(ObjectTestCase):
    def setUp(self):
        self.apply_patch(patch_func('__init__'))
        self.node = objects.Node('1')

    def test_pull(self):
        pass

    def test_get_templates_path(self):
        pass

    def test_pulled(self):
        with patch.dict(self.node.data, {'sha': 'sha', 'app_path': 'path'}):
            self.assertEquals(self.node.pulled, True)
        with patch.dict(self.node.data, {'sha': 'sha', 'app_path': None}):
            self.assertEquals(self.node.pulled, True)
        with patch.dict(self.node.data, {'sha': None, 'app_path': 'path'}):
            self.assertEquals(self.node.pulled, True)
        with patch.dict(self.node.data, {'sha': None, 'app_path': None}):
            self.assertEquals(self.node.pulled, False)

"""
import mongomock
from mock import Mock, patch, PropertyMock, call, DEFAULT
from nose.tools import eq_, raises, assert_in, assert_raises
from flask import Flask
from flask.ext.testing import TestCase
from contextlib import contextmanager

from stretch import agent, testutils
from stretch.agent import objects


class AgentTestCase(TestCase):
    def create_app(self):
        agent.app.config['TESTING'] = True
        return agent.app

    def setUp(self):
        agent.db = self.db = mongomock.Connection().db


class TestLoadBalancer(AgentTestCase):
    @patch('stretch.agent.resources.PersistentObject')
    def test_create(self, obj):
        lb = objects.LoadBalancer.create(_id='1')
        obj.create.assert_invoked_with({'id': '1'})
        lb.start.assert_called_with()


class TestInstance(AgentTestCase):
    def get_instance(self):
        data = {
            '_id': '1',
            'cid': None,
            'node_id': '2',
            'parent_config_key': 'groups/group_id'
        }
        self.db.instances.insert(data)
        return agent.Instance('1')

    @contextmanager
    def mock_fs(self, root):
        mock_fs = testutils.MockFileSystem(root)

        exists_patch = patch('stretch.agent.os.path.exists', mock_fs.exists)
        open_patch = patch('stretch.agent.open', mock_fs.open, create=True)
        walk_patch = patch('stretch.agent.os.walk', mock_fs.walk)

        self.addCleanup(exists_patch.stop)
        self.addCleanup(open_patch.stop)
        self.addCleanup(walk_patch.stop)

        exists_patch.start()
        open_patch.start()
        walk_patch.start()

        yield mock_fs

    def test_get_instances(self):
        rv = self.client.get('/v1/instances')
        self.assertEquals(rv.json, {'results': []})

        data = {
            '_id': '1',
            'cid': None,
            'node_id': '2',
            'parent_config_key': 'groups/group_id'
        }
        self.db.instances.insert(data)
        rv = self.client.get('/v1/instances')
        self.assertEquals(rv.json, {'results': [data]})

    def test_get_instance(self):
        rv = self.client.get('/v1/instances/0')
        self.assertEquals(rv.json, {'message': 'Instance does not exist'})
        self.assertStatus(rv, 404)

        data = {
            '_id': '1',
            'cid': None,
            'node_id': '2',
            'parent_config_key': 'groups/group_id'
        }
        self.db.instances.insert(data)
        rv = self.client.get('/v1/instances/1')
        self.assertEquals(rv.json, data)

    def test_create_instance(self):
        rv = self.client.post('/v1/instances', data={
            'instance_id': '1',
            'node_id': '2',
            'parent_config_key': 'groups/group_id'
        })
        self.assertEquals(rv.json, {
            '_id': '1',
            'cid': None,
            'node_id': '2',
            'parent_config_key': 'groups/group_id'
        })

    def test_should_not_create_duplicate_instance(self):
        self.db.instances.insert({
            '_id': '1',
            'cid': None,
            'node_id': '2',
            'parent_config_key': 'groups/group_id'
        })
        rv = self.client.post('/v1/instances', data={
            'instance_id': '1',
            'node_id': '2',
            'parent_config_key': 'groups/group_id'
        })
        self.assertEquals(rv.json, {'message': 'Instance already exists'})
        self.assertStatus(rv, 409)

    def test_delete_instance(self):
        self.db.instances.insert({'_id': '1', 'cid': None})
        rv = self.client.delete('/v1/instances/1')
        self.assertEquals(rv.data, '')
        self.assertStatus(rv, 204)

    @patch('stretch.agent.Instance.running', new_callable=PropertyMock)
    @patch('stretch.agent.Instance.stop')
    def test_stops_on_delete(self, stop, running):
        instance = self.get_instance()
        running.return_value = True
        instance.delete()
        stop.assert_called_with()

        stop.reset_mock()
        running.return_value = False
        instance.delete()
        assert not stop.called

    @raises(agent.TaskException)
    @patch('stretch.agent.Instance.running', new_callable=PropertyMock)
    def test_should_not_reload_when_stopped(self, running):
        instance = self.get_instance()
        running.return_value = False
        instance.reload()

    @patch('stretch.agent.run_cmd')
    @patch('stretch.agent.Instance.restart')
    @patch('stretch.agent.Instance.running', new_callable=PropertyMock)
    def test_reload(self, running, restart, run_cmd):
        running.return_value = True
        run_cmd.return_value = ('output', 0)
        instance = self.get_instance()
        instance.data['cid'] = 'cid'
        instance.reload()
        run_cmd.assert_called_with(['lxc-attach', '-n', 'cid', '--',
            '/bin/bash', '/usr/share/stretch/files/autoload.sh'])
        assert not restart.called

    @patch('stretch.agent.run_cmd')
    @patch('stretch.agent.Instance.restart')
    @patch('stretch.agent.Instance.running', new_callable=PropertyMock)
    def test_should_restart_when_reload_fails(self, running, restart, run_cmd):
        running.return_value = True
        run_cmd.return_value = ('output', 1)
        instance = self.get_instance()
        instance.data['cid'] = 'cid'
        instance.reload()
        run_cmd.assert_called_with(['lxc-attach', '-n', 'cid', '--',
            '/bin/bash', '/usr/share/stretch/files/autoload.sh'])
        assert restart.called

    @patch('stretch.agent.Instance.running', new_callable=PropertyMock)
    def test_should_only_start_when_ready(self, running):
        instance = self.get_instance()
        running.return_value = True

        with assert_raises(agent.TaskException):
            instance.start()

        running.return_value = False
        instance.get_node = Mock()
        instance.get_node.return_value = None

        with assert_raises(agent.TaskException):
            instance.start()

        node = Mock()
        node.pulled = False
        instance.get_node.return_value = node

        with assert_raises(agent.TaskException):
            instance.start()

    @patch('stretch.agent.run_cmd')
    @patch('stretch.agent.Instance.get_run_args')
    @patch('stretch.agent.Instance.compile_templates')
    @patch('stretch.agent.Instance.running', new_callable=PropertyMock)
    def test_start(self, running, compile_templates, get_run_args, run_cmd):
        instance = self.get_instance()
        running.return_value = False
        instance.get_node = Mock()
        node = Mock()
        instance.get_node.return_value = node
        run_cmd.return_value = ('new_cid', 0)
        instance.start()
        self.assertEquals(instance.data['cid'], 'new_cid')

    def test_running(self):
        instance = self.get_instance()
        instance.data['cid'] = None
        assert not instance.running
        instance.data['cid'] = 'cid'
        assert instance.running

    @patch('stretch.agent.container_dir', '/stretch')
    def test_get_run_args(self):
        instance = self.get_instance()
        instance.get_templates_path = Mock(return_value='/templates')
        node = Mock()
        node.data = {'app_path': None}

        self.assertEquals(instance.get_run_args(node),
            ['-v', '/templates:/stretch/templates:ro'])

        node.data = {'app_path': '/app/path'}
        self.assertEquals(instance.get_run_args(node), ['-v',
            '/templates:/stretch/templates:ro', '-v',
            '/app/path:/stretch/app:ro'])

    @patch('stretch.agent.agent_dir', '/stretch-agent')
    def test_get_templates_path(self):
        instance = self.get_instance()
        instance.data['_id'] = '123'
        self.assertEquals(instance.get_templates_path(),
                          '/stretch-agent/templates/123')

    @patch('stretch.agent.utils.clear_path')
    @patch('stretch.agent.Instance.get_templates_path', return_value='/b')
    def test_compile_templates(self, get_templates_path, clear_path):
        instance = self.get_instance()
        node = Mock()
        node.get_templates_path.return_value = '/a'
        instance.get_node = Mock()
        instance.get_node.return_value = node
        instance.compile_template = Mock()

        with self.mock_fs('/a') as fs:
            fs.set_files({
                'template': '',
                'template.jinja': '',
                'empty': {},
                'sub': {'template': ''}
            })
            instance.compile_templates()

        clear_path.assert_called_with('/b')
        instance.compile_template.assert_has_calls([
            call('template', '/a', '/b', node),
            call('template.jinja', '/a', '/b', node),
            call('sub/template', '/a', '/b', node)
        ], any_order=True)

    @patch.multiple('stretch.agent.utils', makedirs=DEFAULT,
                    render_template_to_file=DEFAULT)
    def test_compile_template(self, makedirs, render_template_to_file):
        instance = self.get_instance()
        instance.data['host_name'] = 'a.example.com'
        instance.data['_id'] = 'instance_id'
        instance.node = node = Mock()
        node.data = {'env_name': 'env', 'sha': None}

        instance.compile_template('template', '/from', '/to', node)
        makedirs.assert_called_with('/to')
        render_template_to_file.assert_called_with('/from/template',
            '/to/template', [{
                'env_name': 'env',
                'host_name': 'a.example.com',
                'instance_id': 'instance_id',
                'release': None
            }]
        )

        makedirs.reset_mock()
        render_template_to_file.reset_mock()
        instance.compile_template('sub/template.JINJA', '/from', '/to', node)
        makedirs.assert_called_with('/to/sub')
        render_template_to_file.assert_called_with('/from/sub/template.JINJA',
            '/to/sub/template', [{
                'env_name': 'env',
                'host_name': 'a.example.com',
                'instance_id': 'instance_id',
                'release': None
            }]
        )


class TestTask(AgentTestCase):
    def test_get_task(self):
        pass

    def test_create_task(self):
        pass


@patch('stretch.agent.app')
def test_run(app):
    instances = [Mock()]
    with patch('stretch.agent.Instance.get_instances', return_value=instances):
        agent.run()
        assert app.run.called
        instances[0].start.assert_called_with()


@patch('stretch.agent.subprocess')
def test_run_cmd(sub):
    p = Mock()
    p.returncode = 0
    p.communicate.return_value = ('stdout', 'stderr')
    sub.Popen.return_value = p
    eq_(agent.run_cmd(['a', 'b']), ('stdout', 0))
    sub.Popen.assert_called_with(['a', 'b'], stdout=sub.PIPE, stderr=sub.PIPE)
"""