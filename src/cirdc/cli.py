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
    for name in ['doctor', 'db-check', 'db-init', 'config-init', 'target-init', 'target-bind', 'target-select',
                 'plan', 'update', 'status', 'resume', 'retry', 'paper', 'analyze', 'mcp', '_worker']:
        child = sub.add_parser(name)
        child.add_argument('--config', default=argparse.SUPPRESS)
        child.add_argument('--json', action='store_true', default=argparse.SUPPRESS)
        if name == 'doctor':
            child.add_argument('--network', action='store_true')
        if name == 'db-init':
            child.add_argument('--adopt', action='store_true')
        if name == 'config-init':
            child.add_argument('--output', required=True)
        if name == 'target-select':
            child.add_argument('--project', default=str(Path.cwd()))
        if name == 'target-init':
            child.add_argument('--ssh', required=True)
            child.add_argument('--remote-config', default='~/.config/cirdc/config.json')
            child.add_argument('--output', required=True)
            child.add_argument('--local-port', type=int, default=33307)
        if name in ('plan', 'update', 'resume', 'retry', 'target-init'):
            child.add_argument('--workers', type=int, choices=range(1, 9), default=4 if name == 'target-init' else None)
        if name in ('plan', 'update'):
            child.add_argument('--publication')
            child.add_argument('--year', type=int)
            child.add_argument('--stage', choices=['all', 'catalog', 'metadata', 'enrich'], default='all',
                               help='New all/metadata jobs include scoped Early Access bibliography refresh by article number')
            child.add_argument('--verify-all', action='store_true',
                               help='Recheck every indexed catalog year and article partition, including historical snapshots')
        if name == 'update':
            child.add_argument('--foreground', action='store_true')
            child.add_argument('--skip-import', action='store_true')
            child.add_argument('--skip-catalog', action='store_true')
            child.add_argument('--max-tasks', type=int)
        if name in ('resume', 'retry', '_worker'):
            child.add_argument('run_id')
        if name in ('resume', 'retry'):
            child.add_argument('--foreground', action='store_true')
            child.add_argument('--max-tasks', type=int, help='New per-session budget; 0 removes the budget')
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
    if filename:
        os.environ['CIRDC_CONFIG'] = str(Path(filename).expanduser().resolve())
    try:
        config = Config.load(filename)
        if command == 'config-init':
            from .profiles import config_init
            value = result(config_init(args['output']))
            print(json.dumps(value, indent=2))
            return 0
        if command == 'target-select':
            from .profiles import select
            value = result(select(config, args['project']))
            print(json.dumps(value, indent=2))
            return 0
        if command == 'target-init':
            from .ssh import configure_target
            value = result(configure_target(args['ssh'], args['remote_config'], args['output'],
                                            args['workers'], args['local_port']))
            print(json.dumps(value, ensure_ascii=False, indent=2))
            return 2 if value['status'] == 'not_ready' else 0
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
        from .schema import SchemaError
        from .ssh import SSHError
        safe = isinstance(error, (ValueError, SchemaError, SSHError))
        print(json.dumps(result({'status': 'error', 'error_type': type(error).__name__,
                                 'code': getattr(error, 'code', 'operation_failed'),
                                 'message': str(error) if safe else 'Operation failed. Run cirdc doctor and inspect the task state.',
                                 **({'database': error.report} if isinstance(error, SchemaError) else {})})))
        return 1


if __name__ == '__main__':
    sys.exit(main())
