import argparse
import json
import os
from pathlib import Path
import sys
from .api import invoke, result
from .config import Config


def parser():
    p = argparse.ArgumentParser(prog='cirdc', description='IEEE publication and article metadata maintenance')
    p.add_argument('--config')
    p.add_argument('--json', action='store_true')
    sub = p.add_subparsers(dest='command', required=True)
    from .author_cli import add_parser
    add_parser(sub)
    web = sub.add_parser('web', help='Authenticated browser and administrator interfaces')
    web.add_argument('--config', default=argparse.SUPPRESS)
    web.add_argument('--json', action='store_true', default=argparse.SUPPRESS)
    web.add_argument('action', choices=['serve', 'init-users', 'passwd', 'index'])
    web.add_argument('--interface', choices=['reader', 'admin'], default='reader')
    web.add_argument('--host')
    web.add_argument('--port', type=int)
    web.add_argument('--username')
    web.add_argument('--max-rows', type=int)
    web.add_argument('--once', action='store_true')
    for name in ['doctor', 'db-init', 'plan', 'update', 'status', 'resume', 'retry', 'paper', 'analyze', 'mcp', '_worker']:
        child = sub.add_parser(name)
        child.add_argument('--config', default=argparse.SUPPRESS)
        child.add_argument('--json', action='store_true', default=argparse.SUPPRESS)
        if name == 'doctor':
            child.add_argument('--network', action='store_true')
        if name in ('plan', 'update'):
            child.add_argument('--publication')
            child.add_argument('--year', type=int)
            child.add_argument('--stage', choices=['all', 'catalog', 'metadata', 'enrich'], default='all')
        if name == 'update':
            child.add_argument('--foreground', action='store_true')
            child.add_argument('--skip-import', action='store_true')
            child.add_argument('--skip-catalog', action='store_true')
            child.add_argument('--max-tasks', type=int)
        if name in ('resume', 'retry', '_worker'):
            child.add_argument('run_id')
        if name in ('resume', 'retry'):
            child.add_argument('--foreground', action='store_true')
        if name == 'status':
            child.add_argument('run_id', nargs='?')
        if name == 'paper':
            child.add_argument('number')
        if name == 'analyze':
            child.add_argument('direction', choices=['references', 'citations', 'tree'])
            child.add_argument('number')
            child.add_argument('--depth', type=int, default=3)
            child.add_argument('--max-nodes', type=int, default=100)
    return p


def main(argv=None):
    args = vars(parser().parse_args(argv))
    filename = args.pop('config', None)
    args.pop('json', False)
    command = args.pop('command')
    previous_config = os.environ.get('CIRDC_CONFIG')
    if filename:
        os.environ['CIRDC_CONFIG'] = str(Path(filename).expanduser().resolve())
    config = Config.load(filename)
    try:
        if command == 'author':
            from .author_cli import invoke_author
            value = invoke_author(config=config, **args)
            print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
            return 1 if value.get('status') == 'error' else 0
        if command == 'web':
            from .web.cli import run
            return run(config, **args)
        if command == 'mcp':
            from .mcp_server import serve
            serve()
            return 0
        if command == '_worker':
            from .engine import Service
            service = Service(config)
            try:
                service.work(args['run_id'])
            finally:
                service.store.close()
            return 0
        if command == 'analyze':
            from .analysis import analyze
            value = result(analyze(config, **args))
        else:
            value = invoke(command, config, **args)
        print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
        return 1 if value.get('status') == 'error' else 2 if value.get('status') == 'not_ready' else 0
    except Exception as error:
        # Never expose SQL connection parameters or upstream HTML through the interface.
        print(json.dumps(result({'status': 'error', 'error_type': type(error).__name__,
                                 'code': getattr(error, 'code', 'operation_failed'),
                                 'message': 'Operation failed. Run cirdc doctor and inspect the task state.'})))
        return 1
    finally:
        if filename:
            if previous_config is None:
                os.environ.pop('CIRDC_CONFIG', None)
            else:
                os.environ['CIRDC_CONFIG'] = previous_config


if __name__ == '__main__':
    sys.exit(main())
