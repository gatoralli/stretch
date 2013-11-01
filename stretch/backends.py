import os
import pyrax
import logging
from fabric.api import run, env, put, cd
from fabric.contrib.files import upload_template
from django.conf import settings

import stretch
from stretch.salt_api import caller_client
from stretch import utils


log = logging.getLogger('stretch')


class Backend(object):
    def __init__(self, options):
        self.options = options
        self.autoloads = False
        self.store_images = options.get('store_images', True)
        # TODO: add in docs that delete_unused_images only happens when
        # store_images is set and a new image is created
        self.delete_unused_images = options.get('delete_unused_images', True)

    def create_host(self, host):
        raise NotImplementedError

    def delete_host(self, host):
        raise NotImplementedError

    def lb_add_host(self, lb, host):
        raise NotImplementedError

    def lb_remove_host(self, lb, host):
        raise NotImplementedError

    def lb_activate_host(self, lb, host):
        raise NotImplementedError

    def lb_deactivate_host(self, lb, host):
        raise NotImplementedError

    def create_lb(self, lb, hosts):
        raise NotImplementedError

    def delete_lb(self, lb):
        raise NotImplementedError

    def require_option(self, name):
        value = self.options.get(name)
        if not value:
            raise Exception('option "%s" does not exist in backend settings'
                            % name)
        return value


class DockerBackend(Backend):
    def __init__(self, options):
        super(DockerBackend, self).__init__(options)
        self.autoloads = True

    def create_host(self, host):
        self.call_salt('stretch.create_host', host.fqdn)
        return None

    def delete_host(self, host):
        self.call_salt('stretch.delete_host', host.fqdn)

    def lb_add_host(self, lb, host):
        self.call_salt('stretch.lb_add_host', lb.backend_id, host.fqdn)

    def lb_remove_host(self, lb, host):
        self.call_salt('stretch.lb_remove_host', lb.backend_id, host.fqdn)

    def lb_activate_host(self, lb, host):
        self.call_salt('stretch.lb_activate_host', lb.backend_id, host.fqdn)

    def lb_deactivate_host(self, lb, host):
        self.call_salt('stretch.lb_deactivate_host', lb.backend_id, host.fqdn)

    def create_lb(self, lb, hosts):
        self.call_salt('stretch.create_lb', [host.fqdn for host in hosts])
        # return lb_id, lb_address
        # TODO: return lb address

    def delete_lb(self, lb):
        self.call_salt('stretch.delete_lb', lb.backend_id)

    def call_salt(self, *args, **kwargs):
        caller_client().function(*args, **kwargs)


class RackspaceBackend(Backend):
    def __init__(self, options):
        super(RackspaceBackend, self).__init__(options)

        self.username = self.require_option('username')
        api_key = self.require_option('api_key')
        self.region = options.get('region', 'DFW').upper()
        self.domainname = self.require_option('domainname')
        self.use_public_network = options.get('use_public_network', False)
        self.image_name = options.get('image', 'Ubuntu 13.04')
        self.flavor_ram = options.get('ram', 1024)

        pyrax.set_setting('identity_type', 'rackspace')
        pyrax.set_credentials(self.username, api_key)
        self.cs = pyrax.connect_to_cloudservers(region=self.region)
        self.clb = pyrax.connect_to_cloud_loadbalancers(region=self.region)

        try:
            self.image = [img for img in self.cs.images.list()
                          if self.image_name in img.name][0]
        except IndexError:
            raise self.ImageNotFound('image "%s" not found' % self.image_name)

        try:
            self.flavor = [flavor for flavor in self.cs.flavors.list()
                           if flavor.ram == self.flavor_ram][0]
        except IndexError:
            raise self.FlavorNotFound('flavor with ram "%s" not found'
                                      % self.flavor_ram)

    def create_host(self, host):
        log.info('Creating host %s...' % host.fqdn)

        image_name, prefix = get_image_name()
        create_image, im_id = self.should_create_image(image_name, prefix)
        image_id = im_id or self.image.id

        server = self.cs.servers.create(host.fqdn, image_id, self.flavor.id)
        pyrax.utils.wait_for_build(server, interval=10)
        if server.status != 'ACTIVE':
            raise Exception('failed to create host')
        log.info('Finished creating host')

        if self.use_public_network:
            address = server.accessIPv4
        else:
            address = server.networks['private'][0]

        self.provision_host(server, address, host, create_image, image_name,
                            prefix)
        log.info('Finished configuring host')
        return address

    def should_create_image(self, image_name, prefix):
        create_image = False
        image_id = None

        if self.store_images:
            images = [i for i in self.cs.images.list() if i.name == image_name]
            if images:
                image = images[0]
                log.info('Using image: %s' % image.name)
                pyrax.utils.wait_until(image, 'status', ['ACTIVE', 'ERROR'],
                                       attempts=0)
                image_id = image.id
            else:
                # Create new image
                create_image = True
                log.info('a new image (%s) will be created from this build'
                         % image_name)
                if self.delete_unused_images:
                    # Delete unused images
                    log.info('Deleting unused images...')
                    for image in self.cs.images.list():
                        if (image.name != image_name and
                                image.name.startswith(prefix)):
                            log.info('Deleting image %s...' % image.name)
                            image.delete()

        return create_image, image_id

    def provision_host(self, server, address, host, create_image, image_name,
                       prefix):
        env.host_string = 'root@%s' % address
        env.password = server.adminPass
        env.disable_known_hosts = True

        script_dir = os.path.join(os.path.dirname(__file__), 'scripts')

        log.info('Provisioning host %s...' % host.fqdn)
        with cd('/root'):
            file_name = 'image-bootstrap.sh'
            put(os.path.join(script_dir, file_name), file_name)
            run('/bin/bash %s' % file_name)

        if create_image:
            # Create image
            log.info('Creating image (%s) from host...' % image_name)
            image_id = server.create_image(image_name)
            image = self.cs.images.get(image_id)
            pyrax.utils.wait_until(image, 'status', ['ACTIVE', 'ERROR'],
                                   attempts=0)
            if image.status != 'ACTIVE':
                raise Exception('failed to create image')

        log.info('Configuring host %s...' % host.fqdn)

        upload_template('host-bootstrap.sh', '/root/host-bootstrap.sh', {
            'hostname': host.hostname,
            'domain_name': host.domain_name,
            'use_public_network': self.use_public_network,
            'etcd_host_address': settings.ETCD_HOST.split(':')[0],
            'etcd_host_port': settings.ETCD_HOST.split(':')[1],
            'master': settings.SALT_MASTER
        }, use_jinja=True, template_dir=script_dir)
        run('/bin/bash /root/host-bootstrap.sh')

    def delete_host(self, host):
        for server in self.cs.list():
            if server.name == host.fqdn:
                server.delete()

    def create_lb(self, lb, hosts):
        if not hosts:
            raise Exception('no hosts defined for load balancer')

        vip = self.clb.VirtualIP(type='PUBLIC')
        nodes = [self.get_node(host, lb) for host in hosts]

        lb_obj = self.clb.create(
            str(utils.generate_random_hex(8)),
            port=lb.port,
            protocol=lb.protocol,
            nodes=nodes,
            virtual_ips=[vip],
            algorithm='LEAST_CONNECTIONS'
        )

        pyrax.utils.wait_for_build(lb_obj)

        if lb_obj.status != 'ACTIVE':
            raise Exception('failed to create load balancer')

        return str(lb_obj.id), lb_obj.sourceAddresses['ipv4Public']

    def delete_lb(self, lb):
        self.clb.get(int(lb.backend_id)).delete()

    def lb_add_host(self, lb, host):
        lb_obj = self.clb.get(int(lb.backend_id))
        node = self.get_node(host, lb)
        lb_obj.add_nodes([node])
        pyrax.utils.wait_for_build(lb_obj)

    def lb_remove_host(self, lb, host):
        lb_obj = self.clb.get(int(lb.backend_id))
        try:
            node = [n for n in lb_obj.nodes if n.address == host.address][0]
        except KeyError:
            raise Exception('failed to get node from load balancer')
        node.delete()
        pyrax.utils.wait_for_build(lb_obj)

    def lb_activate_host(self, lb, host):
        lb_obj = self.clb.get(int(lb.backend_id))
        node = [n for n in lb_obj.nodes if n.address == host.address][0]
        node.condition = 'ENABLED'
        node.update()

    def lb_deactivate_host(self, lb, host):
        lb_obj = self.clb.get(int(lb.backend_id))
        node = [n for n in lb_obj.nodes if n.address == host.address][0]
        node.condition = 'DISABLED'
        node.update()

    def get_node(self, host, lb):
        return self.clb.Node(
            address=host.address,
            port=lb.host_port,
            condition='ENABLED'
        )

    class FlavorNotFound(Exception):
        pass

    class ImageNotFound(Exception):
        pass


def get_image_name():
    prefix = settings.STRETCH_BACKEND_IMAGE_PREFIX
    return '%s-%s' % (prefix, stretch.__version__), prefix


def get_backend(env):
    backend_map = get_backend_map(settings.STRETCH_BACKENDS)
    return backend_map.get(env.system.name, {}).get(env.name)


@utils.memoized
def get_backend_map(backend_dict):
    backend_map = {}

    for system_name, envs in backend_dict.iteritems():
        backend_map[system_name] = {}
        for env_name, backends in envs.iteritems():
            for class_name, options in backends.iteritems():
                # Only one backend per environment
                backend_class = utils.get_class(class_name)
                backend_map[system_name][env_name] = backend_class(options)
                break

    return backend_map
