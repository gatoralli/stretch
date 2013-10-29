from mock import Mock, patch, call
from nose.tools import eq_, assert_raises
import errno

from stretch import utils, testutils


def test_update():
    d = {
        'foo': 1,
        'bar': 2,
        'fubar': {
            'a': 1
        }
    }

    utils.update(d, {
        'bar': 3,
        'foobar': 4,
        'fubar': {
            'a': 5
        }
    })

    eq_(d, {
        'foo': 1,
        'bar': 3,
        'foobar': 4,
        'fubar': {
            'a': 5
        }})


def test_memoized():

    @utils.memoized
    def func():
        return object()

    eq_(func(), func())


@patch('stretch.utils.importlib')
def test_get_class(importlib):
    importlib.import_module.return_value = testutils.mock_attr(klass='foo')
    eq_(utils.get_class('path.to.klass'), 'foo')
    importlib.import_module.assert_called_with('path.to')


@patch('stretch.utils.os')
def test_makedirs(mock_os):

    def mock_makedirs(path):
        err = OSError()
        err.errno = errno.EEXIST
        raise err

    mock_os.path.isdir.return_value = True
    mock_os.makedirs = mock_makedirs
    utils.makedirs('/foo')

    mock_os.path.isdir.return_value = False
    with assert_raises(OSError):
        utils.makedirs('/foo')

    def mock_makedirs(path):
        err = OSError()
        err.errno = 'other'
        raise err

    mock_os.makedirs = mock_makedirs
    mock_os.path.isdir.return_value = True
    with assert_raises(OSError):
        utils.makedirs('/foo')


@patch('stretch.utils.random.choice', return_value='a')
def test_generate_random_hex(choice):
    eq_(utils.generate_random_hex(2), 'aa')
    eq_(utils.generate_random_hex(4), 'aaaa')


@patch('stretch.utils.time')
def test_map_groups(mock_time):
    # TODO: refactor to test batch_size

    on_finish = Mock()

    def callback(item):
        def is_finished():
            return 'result'
        return is_finished

    groups = {'g1': [1, 2, 3], 'g2': [4, 5, 6, 7, 8, 9, 10]}
    result = utils.map_groups(callback, groups, 3, on_finish, 1.0)

    expected_result = [call(_, 'result') for _ in xrange(10)]
    assert testutils.check_items_equal(result, expected_result)
    assert testutils.check_items_equal(on_finish.mock_calls, expected_result)

    mock_time.sleep.assert_called_with(1.0)


def test_group_by_attr():
    m1 = Mock(spec=['a'], a='foo')
    m2 = Mock(spec=['a'], a='bar')
    m3 = Mock(spec=['b'], b='bar')
    group = utils.group_by_attr([m1, m2, m3], 'a')
    eq_(group['foo'], [m1])
    eq_(group['bar'], [m2])
    eq_(group[None], [m3])


def test_path_contains():
    assert utils.path_contains('/a/b', '/a/b/c')
    assert utils.path_contains('/a/b', '/a/b')
    assert not utils.path_contains('/a/b/c', '/a/b')
    assert not utils.path_contains('/a/b', '/b/b')


# Test start to finish of all 4 source to backend transfer methods,
# - if signals are triggered
# - autoloading environments, systems, get_sources, get_backends
