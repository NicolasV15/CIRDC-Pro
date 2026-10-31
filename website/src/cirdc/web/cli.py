import getpass
import json


def bootstrap_users(config, username=None):
    from .auth import Accounts
    users = ([{'username': username, 'role': 'admin'}] if username
             else config.web.get('bootstrap_users', []))
    if not isinstance(users, list) or not users:
        raise ValueError('Set private web.bootstrap_users or pass --username for an initial administrator')
    names = set()
    for user in users:
        if (not isinstance(user, dict) or not Accounts.valid_username(user.get('username'))
                or user.get('role') not in ('reader', 'admin') or user['username'] in names):
            raise ValueError('Bootstrap accounts require unique valid usernames and reader/admin roles')
        names.add(user['username'])
    if not any(user['role'] == 'admin' for user in users):
        raise ValueError('Bootstrap accounts must include an administrator')
    return users


def run(config, action, interface='reader', host=None, port=None, username=None, max_rows=None, once=False):
    if action == 'index':
        if max_rows is not None and max_rows <= 0:
            raise ValueError('Index row budget must be positive')
        from .index import run_index
        print(json.dumps(run_index(config, max_rows=max_rows, once=once), default=str))
    elif action in ('init-users', 'passwd'):
        from .auth import Accounts
        users = bootstrap_users(config, username) if action == 'init-users' else None
        if action == 'passwd' and not Accounts.valid_username(username):
            raise ValueError('Pass --username for the website account to reset')
        password = getpass.getpass('Initial website password: ' if action == 'init-users' else 'New website password: ')
        if not 8 <= len(password) <= 1024:
            raise ValueError('Password must have 8 to 1024 characters')
        accounts = Accounts()
        if action == 'init-users':
            for user in users:
                accounts.create(user['username'], password, role=user['role'])
            print(json.dumps({'status': 'ready', 'accounts': [user['username'] for user in users]}))
        else:
            accounts.reset(username, password)
            print(json.dumps({'status': 'ready'}))
    elif action == 'serve':
        import uvicorn
        from .app import create_app
        if interface == 'admin' and host not in (None, '127.0.0.1', '::1', 'localhost'):
            raise ValueError('The administrator interface must bind to loopback')
        uvicorn.run(create_app(config, interface), host=host or ('127.0.0.1' if interface == 'admin' else '0.0.0.0'),
                    port=port or (18089 if interface == 'admin' else 18088), access_log=False, proxy_headers=False)
    return 0
