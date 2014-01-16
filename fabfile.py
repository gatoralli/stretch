import os
from fabric.api import local, lcd, hide

local_dir = os.path.dirname(os.path.realpath(__file__))


def test():
    with hide('status', 'aborts'):
        local('%s test --rednose --nologcapture' % os.path.join(local_dir, 'manage.py'))


def cov():
    with hide('status', 'aborts'):
        local('%s test --rednose --nologcapture --with-coverage --cover-package=stretch' % os.path.join(local_dir, 'manage.py'))


def build():
    commit = _get_commit()

    with lcd(local_dir):
        _docker_build('stretch/master', commit)

    with lcd(os.path.join(local_dir, 'agent')):
        _docker_build('stretch/agent', commit)


def deploy():
    with lcd(local_dir):
        commit = _get_commit()

        # Use socat SSL tunnel for now
        _deploy_master(commit)
        _deploy_agent(commit)


def _deploy_master(commit):
    tag = 'stretch/master#%s' % commit
    local('docker push %s' % tag)
    run('docker pull stretch/master#abc')

    run('swap containers')


def _deploy_agent(commit):
    tag = 'stretch/agent#%s' % commit
    local('docker push %s' % tag)
    run('docker pull stretch/agent#abc')

    # run: swap agent containers, may need to use stretch python API,
    # or call a stretch hook to deploy the new container


def _docker_build(image, tag):
    local('docker build -t %s#%s .' % (image, tag))


def _get_commit():
    return local('git rev-parse HEAD', capture=True)
