class ServicesContext(object):
    def __init__(self, environment):
        self.services = environment.system.services

    def __getitem__(self, index):
        data = {}
        service = self.services.objects.get(name=attr)
        if service:
            data = service.data
        return data


# TODO: Complete deploy context
def create_deploy_context(deploy):
    return {
        'services': ServicesContext(deploy.environment),
        'environment': deploy.environment,
        'release': deploy.release,
        'existing_release': deploy.existing_release
    }


def create_application_context(): pass
