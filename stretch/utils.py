import os
import errno
import importlib
import lockfile
import string
import shutil
import random
import jinja2
import collections
import subprocess
import tempfile
import cPickle
import time
from distutils import dir_util
from django.conf import settings


class memoized(object):
    """
    Decorator. Caches a function's return value each time it is called.
    If called later with the same arguments, the cached value is returned
    (not reevaluated).
    """
    def __init__(self, func):
        self.func = func
        self.cache = {}

    def __call__(self, *args, **kwargs):
        key = cPickle.dumps(args, 1) + cPickle.dumps(kwargs, 1)
        if not self.cache.has_key(key):
            self.cache[key] = self.func(*args, **kwargs)
        return self.cache[key]


class UrlLocation(object):
    def __init__(self, default, **kwargs):
        self.cert = kwargs.pop('cert', None)
        self.addresses = {'default': default}
        self.addresses.update(kwargs)

    def get_address(self, tag='default'):
        try:
            return self.addresses[tag]
        except KeyError:
            raise KeyError('no addresses exist with tag "%s"' % tag)


def get_class(class_path):
    parts = class_path.split('.')
    module, class_name = '.'.join(parts[:-1]), parts[-1]
    return getattr(importlib.import_module(module), class_name)


def makedirs(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

"""
def lock(name):
    lock_dir = settings.LOCK_DIR
    return lockfile.FileLock(os.path.join(lock_dir, '%s.lock' % name))
"""

def generate_random_hex(length=16):
    hexdigits = '0123456789abcdef'
    return ''.join(random.choice(hexdigits) for _ in xrange(length))


def update(d, u):
    """
    Recursively merge dict-like objects.
    """
    for k, v in u.iteritems():
        if isinstance(v, collections.Mapping):
            d[k] = update(d.get(k, {}), v)
        else:
            d[k] = u[k]
    return d


def render_template_to_file(path, dest=None, contexts=[]):
    context = {}
    [update(context, c) for c in contexts]
    directory, file_name = os.path.split(path)
    loader = jinja2.loaders.FileSystemLoader(directory)
    env = jinja2.Environment(loader=loader)
    data = env.get_template(file_name).render(context)
    with open(dest or path, 'w') as f:
        f.write(data)


def render_template(data, contexts=[]):
    context = {}
    [update(context, c) for c in contexts]
    return jinja2.Template(data).render(context)


def delete_path(path):
    if os.path.exists(path):
        shutil.rmtree(path)


def clear_path(path):
    delete_path(path)
    makedirs(path)


def check_output(*args, **kwargs):
    process = subprocess.Popen(stdout=subprocess.PIPE, *args, **kwargs)
    output, unused_err = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = args[0]
        error = subprocess.CalledProcessError(retcode, cmd)
        error.output = output
        raise error
    return output


def temp_dir(path=None):
    makedirs(settings.STRETCH_TEMP_DIR)
    tmp_path = tempfile.mkdtemp(prefix='%s/' % settings.STRETCH_TEMP_DIR)
    if path:
        dir_util.copy_tree(path, tmp_path)
    return tmp_path


def path_contains(path, file_path):
    return not os.path.relpath(file_path, path).startswith('..')


def group_by_attr(items, attr_name):
    group = {}
    for item in items:
        attr = getattr(item, attr_name, None)
        if attr in group:
            group[attr].append(item)
        else:
            group[attr] = [item]
    return group


def map_groups(callback, groups, batch_size, on_finish=None, interval=1.0):
    results = {}
    pending = dict((key, {}) for key in groups.keys())

    def has_items(group):
        for _, items in group.iteritems():
            if items:
                return True
        return False

    while has_items(groups) or has_items(pending):
        # Queue jobs
        for group, items in groups.iteritems():
            while len(pending[group]) < batch_size and items:
                item = items.pop()
                pending[group][item] = callback(item)

        time.sleep(interval)

        # Collect finished jobs and their results
        for group, items in dict(pending).iteritems():
            for item, is_finished in dict(items).iteritems():
                result = is_finished()
                if result != None:
                    if on_finish:
                        on_finish(item, result)
                    results[item] = result
                    pending[group].pop(item, None)

    return results


def wait(is_finished, interval=2.0):
    while True:
        result = is_finished()
        if result != False:
            return result
        time.sleep(interval)


def run_cmd(cmd, allow_errors=False):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    if p.returncode != 0 and not allow_errors:
        raise Exception(stderr)
    return stdout, p.returncode


def require_options(options, required_options):
    for required_option in required_options:
        if required_option not in options:
            raise KeyError('option "%s" not found' % required_option)
    return options


def generate_memorable_name():  # pragma: no cover
    """
    Return a randomly-generated memorable name.
    """
    adjectives = [
        'afternoon', 'aged', 'ancient', 'autumn', 'billowing',
        'bitter', 'black', 'blue', 'bold', 'broken',
        'calm', 'caring', 'cold', 'cool', 'crimson',
        'damp', 'dark', 'dawn', 'delicate', 'divine',
        'dry', 'empty', 'ephemeral', 'evening', 'falling',
        'fathomless', 'floral', 'fragrant', 'frosty', 'golden',
        'green', 'hidden', 'holy', 'icy', 'imperfect',
        'impermanent', 'late', 'lingering', 'little', 'lively',
        'long', 'majestic', 'mindful', 'misty', 'morning',
        'muddy', 'nameless', 'noble', 'old', 'patient',
        'polished', 'proud', 'purple', 'quiet', 'red',
        'restless', 'rough', 'shy', 'silent', 'silvery',
        'slender', 'small', 'smooth', 'snowy', 'solitary',
        'sparkling', 'spring', 'stately', 'still', 'strong',
        'summer', 'timeless', 'twilight', 'unknowable', 'unmovable',
        'upright', 'wandering', 'weathered', 'white', 'wild',
        'winter', 'wispy', 'withered', 'young',
    ]
    nouns = [
        'bird', 'breeze', 'brook', 'brook', 'bush',
        'butterfly', 'chamber', 'chasm', 'cherry', 'cliff',
        'cloud', 'darkness', 'dawn', 'dew', 'dream',
        'dust', 'eye', 'feather', 'field', 'fire',
        'firefly', 'flower', 'foam', 'fog', 'forest',
        'frog', 'frost', 'glade', 'glitter', 'grass',
        'hand', 'haze', 'hill', 'horizon', 'lake',
        'leaf', 'lily', 'meadow', 'mist', 'moon',
        'morning', 'mountain', 'night', 'paper', 'pebble',
        'pine', 'planet', 'plateau', 'pond', 'rain',
        'resonance', 'ridge', 'ring', 'river', 'sea',
        'shadow', 'shape', 'silence', 'sky', 'smoke',
        'snow', 'snowflake', 'sound', 'star', 'stream',
        'sun', 'sun', 'sunset', 'surf', 'thunder',
        'tome', 'tree', 'violet', 'voice', 'water',
        'waterfall', 'wave', 'wave', 'wildflower', 'wind',
        'wood',
    ]
    return '%s-%s-%s' % (random.choice(adjectives), random.choice(nouns),
                         generate_random_hex(4))
