#!/usr/bin/env python3
"""Initialize an isolated local application database without recording admin credentials."""
import argparse
import getpass
import json
import os
from pathlib import Path
import pwd
import secrets
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user', required=True, help='Local operating-system account owning the private configuration')
    parser.add_argument('--data-root', required=True, help='Dataset location selected by this deployment')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run with sudo so local database administration can use the socket account.')
    account = pwd.getpwnam(args.user)
    config_dir = Path(account.pw_dir) / '.config/cirdc'
    config_file = config_dir / 'config.json'
    if config_file.exists():
        print('Configuration already exists; it was not replaced: ' + str(config_file))
        return
    env = dict(os.environ)
    command = ['mysql', '--protocol=socket', '--user=root', '--batch', '--skip-column-names']
    def sql(statement):
        result = subprocess.run(command, input=statement, text=True, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode:
            raise RuntimeError('Database administration failed; no credential was logged.')
        return result.stdout.strip()
    try:
        sql('SELECT 1;')
    except RuntimeError:
        env['MYSQL_PWD'] = getpass.getpass('MySQL root password (not saved): ')
        sql('SELECT 1;')
    if sql("SELECT COUNT(*) FROM mysql.user WHERE User='cirdc_agent';") != '0':
        raise RuntimeError('cirdc_agent already exists but there is no application configuration. No account was changed.')
    password = secrets.token_urlsafe(36)
    sql("CREATE DATABASE IF NOT EXISTS cirdc CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n"
        f"CREATE USER 'cirdc_agent'@'localhost' IDENTIFIED BY '{password}';\n"
        "GRANT ALL PRIVILEGES ON cirdc.* TO 'cirdc_agent'@'localhost';\n")
    config = {
        'data_root': str(Path(args.data_root).expanduser().resolve()),
        'state_dir': str(Path(account.pw_dir) / '.local/state/cirdc'),
        'mysql': {'host': '127.0.0.1', 'port': 3306, 'database': 'cirdc',
                  'user': 'cirdc_agent', 'password': password},
        'interval': 1.0, 'connect_timeout': 5, 'read_timeout': 30, 'retries': 3,
    }
    config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(config_dir, 0o700)
    os.chown(config_dir, account.pw_uid, account.pw_gid)
    fd, temp = tempfile.mkstemp(dir=config_dir)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(config, f, indent=2)
            f.write('\n')
        os.chown(temp, account.pw_uid, account.pw_gid)
        os.replace(temp, config_file)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    print('CIRDC_DATABASE_READY: ' + str(config_file))


if __name__ == '__main__':
    main()
