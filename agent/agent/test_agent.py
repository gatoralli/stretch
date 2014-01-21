import pymongo

from twisted.internet import defer, reactor
from twisted.trial.unittest import TestCase
from .server import Agent, db_client, AgentServerProtocol
from autobahn.twisted.websocket import connectWS, listenWS
from autobahn.wamp import (WampServerFactory, WampClientFactory,
                           WampClientProtocol)


db_client = pymongo.MongoClient()
db_name = 'stretch-agent-test'
db = db_client[db_name]
agent = Agent(db_name)


class ClientProtocol(WampClientProtocol):

    openHandshakeTimeout = 0

    def onSessionOpen(self):
        self.factory.protocol = self
        self.factory.onSessionOpen.callback(self)

    def connectionMade(self):
        WampClientProtocol.connectionMade(self)
        self.factory.onConnectionMade.callback(self)

    def connectionLost(self, *args):
        WampClientProtocol.connectionLost(self, *args)
        self.factory.onConnectionLost.callback(self)


class ServerProtocol(AgentServerProtocol):

    def __init__(self):
        AgentServerProtocol.__init__(self, agent)

    def connectionLost(self, *args):
        AgentServerProtocol.connectionLost(self, *args)
        self.factory.onConnectionLost.callback(self)


class TestAgent(TestCase):

    def setUp(self):
        self.resetDatabase()

        self.serverDisconnected = defer.Deferred()
        connected = defer.Deferred()
        opened = defer.Deferred()

        self.serverPort = self._listenServer(self.serverDisconnected)
        self.clientDisconnected = defer.Deferred()
        self.clientConnection = self._connectClient(connected, opened,
                                                    self.clientDisconnected)
        return defer.gatherResults([connected, opened])

    def resetDatabase(self):
        db_client.drop_database(db_name)

    def _listenServer(self, d):
        factory = WampServerFactory('ws://localhost:9000', debugWamp=True)
        factory.protocol = ServerProtocol
        factory.onConnectionLost = d
        return listenWS(factory)

    def _connectClient(self, connected, opened, clientDisconnected):
        factory = WampClientFactory('ws://localhost:9000', debugWamp=True)
        factory.protocol = ClientProtocol
        factory.onConnectionMade = connected
        factory.onSessionOpen = opened
        factory.onConnectionLost = clientDisconnected
        self.factory = factory
        return connectWS(factory)

    def tearDown(self):
        stopListening = defer.maybeDeferred(self.serverPort.stopListening)

        self.clientConnection.disconnect()
        self.resetDatabase()

        return defer.gatherResults([stopListening, self.clientDisconnected,
                                    self.serverDisconnected])

    def call(self, *args, **kwargs):
        return self.factory.protocol.call(*args, **kwargs)

    @defer.inlineCallbacks
    def test_add_node(self):
        content = yield self.call('ns#add_node', '1')
        self.assertEquals(content, None)
        self.assertEquals(db['nodes'].find({'_id': '1'}).count(), 1)

    @defer.inlineCallbacks
    def test_remove_node(self):
        db['nodes'].insert({'_id': '1'})

        content = yield self.call('ns#remove_node', '1')
        self.assertEquals(content, None)
        self.assertEquals(db['nodes'].find({'_id': '1'}).count(), 0)

    @defer.inlineCallbacks
    def test_update_node(self):
        db['nodes'].insert({'_id': '1'})

        content = yield self.call('ns#pull_node', '1')

        """
        Options:

        - app_path (local path if deploying from source)
        - sha (release sha)
        - env_id
        - env_name
        - image (name)
        - ports (ports [in the container] to expose on the containing host)

        """

        self.assertEquals(content, None)
        self.assertEquals(db['nodes'].find({'_id': '1'}).count(), 0)

    @defer.inlineCallbacks
    def test_add_instance(self):

        """
        Options:

        - node_id
        - host_name
        - config_key

        Process configuration with context = {
            'env_name': self.node.data['env_name'],
            'host_name': self.data['host_name'],
            'instance_id': self.data['_id'],
            'release': self.node.data['sha']
        }
        """
        pass

    @defer.inlineCallbacks
    def test_remove_instance(self):
        pass

    @defer.inlineCallbacks
    def test_reload_instance(self):
        pass

    @defer.inlineCallbacks
    def test_restart_instance(self):
        pass

    # part of the reactor needs to loop and check running containers to reboot on crash
    # or persist to etcd

    # interface with supervisor? "docker start/exec and logging?"
    # Agent should be set to reboot through host's supervisor

    # if not using supervisor how are:

    #   - autorestarts
    #   - logging
    #   - etcd push
