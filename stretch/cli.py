"""
stretch

Usage: stretch [--version] [--debug] [--config=<path>] [options]
               <command> [<args>...]

Options:
   -h, --help
   -l <log_level>, --log-level=<log_level>

The most commonly used stretch commands are:
   create     Create an object
   destroy    Destroy an object
   deploy     Deploy a release to an environment
   scale      Scale a group
   ls         List details about an object

See 'stretch <command> help' for more information on a specific command.

"""
import os
import sys
import logging
from docopt import docopt, DocoptExit

import stretch
from stretch import config, objects

log = logging.getLogger(__name__)


class Cli(object):
    def create(self, args):
        """
        stretch create

        Usage:
           stretch create system <system_path>
           stretch create environment <environment_path>
           stretch create group <group_path> <node> [--size=n]
           stretch create release <source_name> [<option>=<val> ...] [--id=id]

        Options:
           --size=n  Amount of nodes to add initially [default: 0]
           --id=id   Manually give the release an id

        """
        if args['system']:
            objects.create_system(args['<system_path>'])
        elif args['environment']:
            objects.create_environment(args['<environment_path>'])
        elif args['group']:
            objects.create_group(
                args['<group_path>'],
                args['<node>'],
                args['<amount>']
            )
        elif args['release']:
            options = {}
            for option in args['<option>=<val>']:
                fragments = option.split('=')
                options[fragments[0]] = '='.join(fragments[1:])

            print objects.create_release(
                args['<source_name>'],
                options,
                args['--id']
            )

    def destroy(self, args):
        """
        stretch destroy

        Usage:
           stretch destroy <object_path>

        """
        objects.destroy_object(object_path)


    def deploy(self, args):
        """
        stretch deploy

        Usage: stretch deploy <release_identifier> <environment>

        The release_identifier can either be an id or a name.

        """
        objects.deploy(args['<release_identifier>'], args['<environment>'])

    def scale(self, args):
        """
        stretch scale

        Usage: stretch scale <group_path> (up|down|to) <amount> [--routing]

        Options:
           --routing  Scale the routing layer instead of the host layer

        """
        try:
            amount = int(args['<amount>'])
        except ValueError:
            raise ValueError('Scaling amount must be an integer.')

        if amount < 0:
            raise ValueError('Scaling amount should be >= 0.')

        routing = args['--routing']
        print routing

        if args['up']:
            scale_up(args['<group_path>'], amount, routing)
        if args['down']:
            scale_down(args['<group_path>'], amount, routing)
        if args['up']:
            scale_to(args['<group_path>'], amount, routing)

    def ls(self, args):
        """
        stretch ls

        Usage:
           stretch ls (--releases|--systems)
           stretch ls <object_path>

        """
        if args['--releases']:
            objects.list_releases()
        elif args['--systems']:
            list_systems()
        else:
            list_children_of(get_object(args['<object_path>']))


def trim(docstring):
    """
    Function to trim whitespace from docstring

    c/o PEP 257 Docstring Conventions
    <http://www.python.org/dev/peps/pep-0257/>
    """
    if not docstring:
        return ''
    # Convert tabs to spaces (following the normal Python rules)
    # and split into a list of lines:
    lines = docstring.expandtabs().splitlines()
    # Determine minimum indentation (first line doesn't count):
    indent = sys.maxint
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped:
            indent = min(indent, len(line) - len(stripped))
    # Remove indentation (first line is special):
    trimmed = [lines[0].strip()]
    if indent < sys.maxint:
        for line in lines[1:]:
            trimmed.append(line[indent:].rstrip())
    # Strip off trailing and leading blank lines:
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    while trimmed and not trimmed[0]:
        trimmed.pop(0)
    # Return a single string:
    return '\n'.join(trimmed)


def start_logger():
    console_handler = logging.StreamHandler(stream=sys.stderr)
    console_handler.setLevel(logging.INFO)
    root_logger = logging.getLogger()
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.DEBUG)

    return console_handler


def main():
    console_handler = start_logger()

    cli = Cli()
    args = docopt(__doc__, version='stretch %s' % stretch.__version__,
                  options_first=True)

    cmd = args['<command>']

    if args['--config']:
        config.set_config_file(args['--config'])
    elif os.environ.get('STRETCH_CONFIG'):
        config.set_config_file(os.environ.get('STRETCH_CONFIG'))

    if args['--log-level'] == 'debug':
        console_handler.setLevel(logging.DEBUG)
    elif args['--log-level'] == 'info':
        console_handler.setLevel(logging.INFO)
    elif args['--log-level'] == 'warning':
        console_handler.setLevel(logging.WARNING)
    elif args['--log-level'] == 'error':
        console_handler.setLevel(logging.ERROR)
    elif args['--log-level'] == 'critical':
        console_handler.setLevel(logging.CRITICAL)

    if args['--log-level']:
        format = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        console_handler.setFormatter(logging.Formatter(format))

    if cmd == 'help':
        docopt(__doc__, argv=['--help'])

    if hasattr(cli, cmd):
        method = getattr(cli, cmd)
    else:
        raise DocoptExit("%r is not a stretch command. "
                         "See `stretch help`." % cmd)

    argv = [args['<command>']] + args['<args>']
    docstring = trim(method.__doc__)

    if args['<args>'] and args['<args>'][0] == 'help':
        args.update(docopt(docstring, argv=['--help']))
    if 'Usage:' in docstring:
        args.update(docopt(docstring, argv=argv))

    method(args)
