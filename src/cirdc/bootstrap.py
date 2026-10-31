"""Explicit provisioning of a new, isolated local MySQL schema."""
import argparse
import getpass
from pathlib import Path
import re
import secrets

from .profiles import save_private


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--data-root', required=True)
    parser.add_argument('--database', default='cirdc')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=3306)
    parser.add_argument('--admin-user', default='root')
    parser.add_argument('--admin-socket')
    parser.add_argument('--account-host', default='localhost')
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', args.database):
        parser.error('Use a simple database identifier')
    output = Path(args.output).expanduser().resolve()
    if output.exists() or any((p / '.git').exists() for p in output.parents):
        parser.error('Select a new private profile path outside Git checkouts')
    import pymysql
    options = {'host': args.host, 'port': args.port, 'user': args.admin_user,
               'password': getpass.getpass('Database administrator password (not saved): '),
               'autocommit': True, 'charset': 'utf8mb4'}
    if args.admin_socket:
        options['unix_socket'] = args.admin_socket
    admin = pymysql.connect(**options)
    account = 'cirdc_' + secrets.token_hex(6)
    password = secrets.token_urlsafe(36)
    try:
        with admin.cursor() as cursor:
            cursor.execute('SELECT SCHEMA_NAME FROM information_schema.schemata WHERE SCHEMA_NAME=%s', (args.database,))
            if cursor.fetchone():
                raise ValueError('Database already exists; configure and inspect it instead of provisioning over it')
            cursor.execute(f'CREATE DATABASE `{args.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
            cursor.execute('CREATE USER %s@%s IDENTIFIED BY %s', (account, args.account_host, password))
            cursor.execute(f'GRANT ALL PRIVILEGES ON `{args.database}`.* TO %s@%s', (account, args.account_host))
    finally:
        admin.close()
    root = Path(args.data_root).expanduser().resolve()
    value = {'data_root': str(root), 'state_dir': str(Path.home() / '.local/state/cirdc'),
             'mysql': {'host': args.host, 'port': args.port, 'database': args.database, 'user': account, 'password': password},
             'workers': 1, 'interval': 1, 'connect_timeout': 5, 'read_timeout': 30, 'retries': 3}
    save_private(output, value)
    from .api import invoke
    from .config import Config
    result = invoke('db-init', Config.load(output))
    if result['status'] != 'ready':
        raise RuntimeError('Database created; initialization needs attention. Run db-check with the private profile.')
    for name in ('all_journals.json', 'all_conferences.json'):
        target = root / 'publicationInfo' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text('{}\n')
    print('CIRDC_DATABASE_READY: ' + str(output))


if __name__ == '__main__':
    main()
