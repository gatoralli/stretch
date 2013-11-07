from flask.ext.restful import reqparse, Resource

from stretch.agent.loadbalancer_server import get_client
from stretch.agent import api, resources, db


class LoadBalancer(resources.PersistentObject):
    name = 'loadbalancer'

    @classmethod
    def create(cls, args):
        super(LoadBalancer, self).create(args)
        self.start()

    def delete(self):
        db.endpoints.remove({'lb_id': self.data['_id']})
        self.stop()
        super(Instance, self).delete()

    def start(self):
        get_client().start_lb(self.data['_id'])

    def stop(self):
        get_client().stop_lb(self.data['_id'])

    @classmethod
    def start_all(cls):
        [lb.start() for lb in cls.get_lbs()]

    @classmethod
    def get_lbs(cls):
        for lb in self.collection.find(fields=['_id']):
            yield cls(lb['_id'])


class LoadBalancerListResource(resources.ObjectListResource):
    obj_class = LoadBalancer


class LoadBalancerResource(resources.ObjectResource):
    obj_class = LoadBalancer


class EndpointListResource(Resource):
    def post(self, lb_id):
        args = self.parse_args()
        args['lb_id'] = lb_id
        db.endpoints.insert(args)
        get_client().add_endpoint(lb_id, (args['host'], args['port']))
        return '', 201

    def delete(self, lb_id):
        args = self.parse_args()
        args['lb_id'] = lb_id
        db.endpoints.remove(args)
        get_client().remove_endpoint(lb_id, (args['host'], args['port']))
        return '', 204

    def parse_args(self):
        parser = reqparse.RequestParser()
        parser.add_argument('host', type=str, required=True)
        parser.add_argument('port', type=int, required=True)
        return parser.parse_args()


resources.add_api_resource('loadbalancers', LoadBalancerResource,
                           LoadBalancerListResource)
api.add_resource(EndpointListResource,
                 '/v1/loadbalancers/<string:loadbalancer_id>/endpoints')
