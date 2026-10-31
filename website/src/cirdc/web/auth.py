import hashlib
import re
import secrets
import time
from contextlib import contextmanager
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from .settings import connect


class Accounts:
    def __init__(self):
        self.hasher = PasswordHasher()
        self.dummy = self.hasher.hash(secrets.token_urlsafe(32))
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS users(
              username TEXT PRIMARY KEY,password_hash TEXT NOT NULL,role TEXT NOT NULL,
              active INTEGER NOT NULL DEFAULT 1,must_change INTEGER NOT NULL DEFAULT 1,
              created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(
              token_hash TEXT PRIMARY KEY,username TEXT NOT NULL,interface TEXT NOT NULL,
              csrf TEXT NOT NULL,expires REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS session_user ON sessions(username);
            CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY,username TEXT,ip TEXT,at REAL);
            CREATE INDEX IF NOT EXISTS attempt_time ON attempts(at);
            CREATE TABLE IF NOT EXISTS audit(
              id INTEGER PRIMARY KEY,at REAL NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,
              target TEXT NOT NULL,detail TEXT NOT NULL);
            ''')

    @contextmanager
    def db(self):
        db = connect('accounts.sqlite')
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def valid_username(username):
        return isinstance(username, str) and re.fullmatch(r'[a-z][a-z0-9_-]{0,31}', username)

    def create(self, username, password, role='reader', actor='bootstrap'):
        if not self.valid_username(username) or len(password) < 8 or len(password) > 1024 or role not in ('reader', 'admin'):
            raise ValueError('Invalid account or password (minimum 8 characters)')
        value = self.hasher.hash(password)
        with self.db() as db:
            inserted = db.execute('INSERT OR IGNORE INTO users(username,password_hash,role,created) VALUES(?,?,?,?)',
                                  (username, value, role, time.time())).rowcount
            if not inserted:
                if actor != 'bootstrap':
                    raise ValueError('Account already exists')
                return False
            self.audit(actor, 'account_create', username, '', db)
            return True

    def audit(self, actor, action, target='', detail='', db=None):
        if db is None:
            with self.db() as connection:
                self.audit(actor, action, target, detail, connection)
            return
        db.execute('INSERT INTO audit(at,actor,action,target,detail) VALUES(?,?,?,?,?)',
                   (time.time(), actor, action, str(target), str(detail)[:1000]))

    def login(self, username, password, interface, ip):
        if not isinstance(username, str) or not isinstance(password, str) or len(password) > 1024:
            raise ValueError('Invalid credentials')
        with self.db() as db:
            db.execute('DELETE FROM attempts WHERE at<?', (time.time() - 900,))
            failures = db.execute('SELECT COUNT(*) FROM attempts WHERE username=? OR ip=?', (username, ip)).fetchone()[0]
            if failures >= 5:
                raise PermissionError('Too many attempts; try again in 15 minutes')
            user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        try:
            correct = self.hasher.verify(user['password_hash'] if user else self.dummy, password)
        except (VerificationError, InvalidHashError):
            correct = False
        allowed = correct and user and user['active'] and (interface != 'admin' or user['role'] == 'admin')
        if not allowed:
            with self.db() as db:
                db.execute('INSERT INTO attempts(username,ip,at) VALUES(?,?,?)', (username, ip, time.time()))
                self.audit(username, 'login_failed', '', '', db)
            raise ValueError('Username or password is incorrect')
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
            db.execute('DELETE FROM attempts WHERE username=?', (username,))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?,?)',
                       (hashlib.sha256(token.encode()).hexdigest(), username, interface, csrf,
                        time.time() + (3600 if interface == 'admin' else 28800)))
            self.audit(username, 'login', interface, '', db)
        return token, {'username': username, 'role': user['role'], 'must_change': bool(user['must_change']), 'csrf': csrf}

    def session(self, token, interface):
        if not token:
            return None
        with self.db() as db:
            row = db.execute('SELECT u.username,u.role,u.must_change,s.csrf FROM sessions s '
                             'JOIN users u ON u.username=s.username WHERE token_hash=? '
                             'AND s.interface=? AND s.expires>? AND u.active=1',
                             (hashlib.sha256(token.encode()).hexdigest(), interface, time.time())).fetchone()
            if not row:
                return None
            result = dict(row)
            result['must_change'] = bool(result['must_change'])
            return result

    def logout(self, token):
        with self.db() as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),))

    def change(self, username, current_password, new_password):
        if not isinstance(new_password, str) or len(new_password) < 8 or len(new_password) > 1024:
            raise ValueError('New password must have 8 to 1024 characters')
        with self.db() as db:
            row = db.execute('SELECT password_hash FROM users WHERE username=?', (username,)).fetchone()
        try:
            self.hasher.verify(row['password_hash'], current_password)
        except VerificationError:
            raise ValueError('Current password is incorrect') from None
        try:
            same = self.hasher.verify(row['password_hash'], new_password)
        except VerificationError:
            same = False
        if same:
            raise ValueError('Choose a different password')
        self.reset(username, new_password, must_change=False, actor=username)

    def reset(self, username, password, must_change=True, actor='local-cli'):
        if not isinstance(password, str) or not 8 <= len(password) <= 1024:
            raise ValueError('Password must have 8 to 1024 characters')
        value = self.hasher.hash(password)
        with self.db() as db:
            if not db.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone():
                raise ValueError('Unknown account')
            db.execute('UPDATE users SET password_hash=?,must_change=? WHERE username=?', (value, int(must_change), username))
            db.execute('DELETE FROM sessions WHERE username=?', (username,))
            self.audit(actor, 'password_reset', username, '', db)

    def disable(self, username, active, actor):
        if username == actor and not active:
            raise ValueError('The current administrator cannot disable their own account')
        with self.db() as db:
            if not db.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone():
                raise ValueError('Unknown account')
            db.execute('UPDATE users SET active=? WHERE username=?', (int(active), username))
            db.execute('DELETE FROM sessions WHERE username=?', (username,))
            self.audit(actor, 'account_enable' if active else 'account_disable', username, '', db)

    def list(self):
        with self.db() as db:
            return [dict(r) for r in db.execute('SELECT username,role,active,must_change,created FROM users ORDER BY username')]

    def events(self):
        with self.db() as db:
            return [dict(r) for r in db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 100')]
