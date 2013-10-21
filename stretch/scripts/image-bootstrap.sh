#!/bin/bash
export DEBIAN_FRONTEND=noninteractive

# Install salt and docker
apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 7F0CEB10
echo 'deb http://downloads-distro.mongodb.org/repo/ubuntu-upstart dist 10gen' | sudo tee /etc/apt/sources.list.d/mongodb.list
apt-get install -y curl linux-image-extra-`uname -r`
curl -L http://get.docker.io | sh
curl -L http://bootstrap.saltstack.org | sh

# Install prerequisites for stretch agent
# TODO: use unix domain socket instead of TCP connection for mongodb
apt-get install -y ufw
ufw deny 27017
mkdir -p /var/lib/stretch/agent
apt-get install -y python-pip mongodb-10gen
pip install pymongo==2.6.3 Jinja2==2.7 docker-py==0.2.1
# TODO: Implement production-ready process management when Docker supports it
# TODO: ensure that rc.local runs on startup
echo "python /var/cache/salt/minion/extmods/modules/stretch.py" >> /etc/rc.local

export DEBIAN_FRONTEND=dialog
