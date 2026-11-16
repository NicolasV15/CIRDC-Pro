"""Session, sign-in, self-registration and password routes shared by the site and the offline demo."""
import os
import secrets

from starlette.concurrency import run_in_threadpool
from starlette.routing import Route


def registration_open(interface, public_reader, value=None):
    """Self-registration is open on public readers and closed where readers must already have an account."""
    if interface != 'reader':
        return False
    value = value if value is not None else os.environ.get('CIRDC_WEB_REGISTRATION', '')
    if value not in ('', 'open', 'closed'):
        raise ValueError('CIRDC_WEB_REGISTRATION must be open or closed')
    return value == 'open' or value == '' and public_reader


def auth_routes(accounts, interface, public_reader, registration, response, body):
    cookie = 'cirdc_' + interface
    pre_cookie = 'cirdc_pre_' + interface
    lifetime = 3600 if interface == 'admin' else 28800

    def client(request):
        return request.client.host if request.client else ''

    async def session(request):
        user = request.state.user
        value = {'user': user, 'interface': interface, 'registration': registration,
                 'authentication_required': not public_reader, 'access_mode': 'public' if public_reader else 'required'}
        if user:
            return response({**value, 'csrf': user['csrf']})
        # Anonymous public visitors get no cookie unless they open the sign-in or registration form.
        if public_reader and request.query_params.get('prepare') != '1':
            return response({**value, 'csrf': ''})
        csrf = secrets.token_urlsafe(32)
        result = response({**value, 'csrf': csrf})
        result.set_cookie(pre_cookie, csrf, httponly=True, samesite='strict', max_age=3600)
        return result

    def pre_login_checked(request):
        token = request.cookies.get(pre_cookie, '')
        return bool(token) and secrets.compare_digest(token, request.headers.get('x-csrf-token', ''))

    def signed_in(user, token):
        result = response({'user': user, 'csrf': user['csrf']})
        result.set_cookie(cookie, token, httponly=True, samesite='strict', max_age=lifetime)
        result.delete_cookie(pre_cookie)
        return result

    async def login(request):
        if not pre_login_checked(request):
            return response({'error': 'csrf_rejected'}, 403)
        try:
            data = await body(request)
            token, user = await run_in_threadpool(accounts.login, data.get('username'), data.get('password'),
                                                  interface, client(request))
        except PermissionError:
            return response({'error': 'login_throttled', 'message': '尝试过多，请 15 分钟后重试。'}, 429)
        except (ValueError, KeyError, TypeError):
            return response({'error': 'invalid_credentials', 'message': '用户名或密码不正确。'}, 401)
        return signed_in(user, token)

    async def register(request):
        if not registration:
            return response({'error': 'not_found'}, 404)
        if not pre_login_checked(request):
            return response({'error': 'csrf_rejected'}, 403)
        try:
            data = await body(request)
            username, password = data.get('username'), data.get('password')
            await run_in_threadpool(accounts.register, username, password, client(request))
            token, user = await run_in_threadpool(accounts.login, username, password, interface, client(request))
        except FileExistsError:
            return response({'error': 'username_taken'}, 409)
        except PermissionError:
            return response({'error': 'registration_throttled'}, 429)
        except (ValueError, KeyError, TypeError):
            return response({'error': 'invalid_registration'}, 422)
        return signed_in(user, token)

    def logout(request):
        accounts.logout(request.cookies.get(cookie, ''))
        result = response({'status': 'signed_out'})
        result.delete_cookie(cookie)
        return result

    async def password(request):
        if not request.state.user:
            return response({'error': 'authentication_required'}, 401)
        try:
            data = await body(request)
            await run_in_threadpool(accounts.change, request.state.user['username'], data.get('current_password'),
                                    data.get('new_password'))
        except (ValueError, TypeError):
            return response({'error': 'invalid_password', 'message': '请核对当前密码，新密码至少 8 个字符且不能与原密码相同。'}, 422)
        result = response({'status': 'password_changed'})
        result.delete_cookie(cookie)
        return result

    routes = [Route('/api/auth/session', session), Route('/api/auth/login', login, methods=['POST']),
              Route('/api/auth/logout', logout, methods=['POST']), Route('/api/auth/password', password, methods=['POST'])]
    if registration:
        routes.append(Route('/api/auth/register', register, methods=['POST']))
    return routes


def admin_account_routes(accounts, response, body):
    """Administrator account management: list, audit, create, reset and enable/disable."""
    def users(request):
        return response({'items': accounts.list()})

    def audit(request):
        return response({'items': accounts.events()})

    async def user_action(request):
        try:
            data = await body(request)
            name = data.get('username')
            actor = request.state.user['username']
            action = request.path_params['action']
            if action == 'create':
                await run_in_threadpool(accounts.create, name, data.get('password', ''), 'reader', actor)
            elif action == 'reset':
                await run_in_threadpool(accounts.reset, name, data.get('password', ''), True, actor)
            elif action == 'active':
                if not isinstance(data.get('active'), bool):
                    raise ValueError()
                await run_in_threadpool(accounts.disable, name, data['active'], actor)
            else:
                return response({'error': 'not_found'}, 404)
        except (ValueError, TypeError):
            return response({'error': 'invalid_account_action', 'message': '账户操作无效，请检查用户名或密码。'}, 422)
        return response({'status': 'ok'})

    return [Route('/api/admin/users', users), Route('/api/admin/users/{action}', user_action, methods=['POST']),
            Route('/api/admin/audit', audit)]
