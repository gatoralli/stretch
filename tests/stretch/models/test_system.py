from mock import Mock, patch
from nose.tools import eq_, raises

from stretch import models, exceptions


class TestSystem(object):
    @raises(exceptions.UndefinedSource)
    @patch('stretch.sources.get_sources')
    def test_source(self, get_sources):
        get_sources.return_value = ['foo']
        system = models.System(name='system')
        eq_(system.source, 'foo')
        get_sources.return_value = []
        system = models.System(name='bar')
        system.source

    @patch('stretch.models.System.environments')
    @patch('stretch.models.System.source')
    @patch('stretch.models.Environment.backend')
    def test_initial_sync_source(self, backend, source, environments):
        source.autoload = True
        env = Mock()
        env.backend.autoloads = True
        environments.all.return_value = [env]
        system = models.System(name='system')
        system.sync_source()
        env.deploy.delay.assert_called_with(source)

        env.backend.autoloads = False
        env.deploy.delay.reset_mock()
        system.sync_source()
        assert not env.deploy.delay.called

        source.autoload = False
        env.backend.autoloads = True
        env.deploy.delay.reset_mock()
        system.sync_source()
        assert not env.deploy.delay.called

    @patch('stretch.models.System.environments')
    @patch('stretch.models.System.source')
    @patch('stretch.models.Environment.backend')
    def test_sync_source(self, backend, source, environments):
        source.autoload = True
        env = Mock()
        env.backend.autoloads = True
        environments.all.return_value = [env]
        system = models.System(name='system')
        system.sync_source(['foo', 'bar'])
        env.autoload.delay.assert_called_with(source, ['foo', 'bar'])

        env.backend.autoloads = False
        env.autoload.delay.reset_mock()
        system.sync_source(['foo', 'bar'])
        assert not env.autoload.delay.called

        source.autoload = False
        env.backend.autoloads = True
        env.autoload.delay.reset_mock()
        system.sync_source(['foo', 'bar'])
        assert not env.autoload.delay.called
