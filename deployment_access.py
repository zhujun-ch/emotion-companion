"""Explicit origins, hosts and reviewer networks for local and deployed access."""
import os
from ipaddress import ip_address, ip_network
from pathlib import Path
from time import time

from flask import abort, jsonify, request
from flask_cors import CORS


def read_secret(name):
    filename = os.getenv(name + '_FILE')
    return (Path(__file__).parent / filename).read_text(encoding='utf-8').strip() if filename else os.getenv(name, '')


def configure_access(app):
    production = os.getenv('APP_ENV', 'development') == 'production'
    origins = [v.strip() for v in os.getenv('APP_ALLOWED_ORIGINS',
               'http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174').split(',') if v.strip()]
    hosts = [v.strip() for v in os.getenv('APP_TRUSTED_HOSTS', 'localhost,127.0.0.1,[::1]').split(',') if v.strip()]
    networks = [ip_network(v.strip()) for v in os.getenv('REVIEWER_ALLOWED_NETWORKS', '127.0.0.0/8,::1/128').split(',') if v.strip()]
    if not origins or any('*' in value or value == 'null' or not value.startswith(('http://', 'https://')) for value in origins):
        raise RuntimeError('APP_ALLOWED_ORIGINS 必须是明确的网页来源列表')
    if not hosts or any('*' in value for value in hosts):
        raise RuntimeError('APP_TRUSTED_HOSTS 必须是明确的主机列表')
    if production:
        required = ('APP_ALLOWED_ORIGINS', 'APP_TRUSTED_HOSTS', 'REVIEWER_ALLOWED_NETWORKS')
        if any(not os.getenv(key) for key in required) or not networks or any(n.prefixlen == 0 for n in networks):
            raise RuntimeError('生产环境必须显式配置来源、主机与审核员访问网段')
        if any(not origin.startswith('https://') for origin in origins):
            raise RuntimeError('生产网页来源必须使用 HTTPS')
        if os.getenv('ENABLE_DEMO_PAGES') == '1' and (not read_secret('DEMO_REVIEWER_PASSWORD_HASH') or read_secret('DEMO_REVIEWER_PASSWORD')):
            raise RuntimeError('生产审核员必须使用密码哈希，不能配置明文演示口令')
    app.config.update(TRUSTED_HOSTS=hosts, MAX_CONTENT_LENGTH=32 * 1024)
    CORS(app, resources={r'/api/*': {'origins': origins}},
         allow_headers=['Authorization', 'Content-Type', 'X-Treehole-Token', 'X-Request-ID'],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'], supports_credentials=False)

    @app.before_request
    def check_access():
        origin = request.headers.get('Origin')
        if origin and origin not in origins:
            abort(403, '当前网页来源不允许访问')
        if request.path.startswith('/api/demo/review/'):
            try:
                allowed = any(ip_address(request.remote_addr) in network for network in networks)
            except ValueError:
                allowed = False
            if not allowed:
                abort(403, '当前网络不允许访问审核接口')

    @app.after_request
    def private_response(response):
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
            response.headers['X-Content-Type-Options'] = 'nosniff'
        return response


def initialize_attempts(db):
    db.execute('''CREATE TABLE IF NOT EXISTS credential_attempt (
        bucket TEXT PRIMARY KEY, attempts INTEGER NOT NULL, reset_at INTEGER NOT NULL)''')


def consume_attempt(connect, namespace, username):
    """Shared across workers; no passwords or bearer tokens enter these rows."""
    from hashlib import sha256
    now = int(time())
    identity = sha256(str(username).lower().encode()).hexdigest()
    limited = False
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM credential_attempt WHERE reset_at <= ?', (now,))
        for key, limit in ((f'{namespace}:ip:{request.remote_addr}', 40),
                           (f'{namespace}:user:{identity}', 10)):
            row = db.execute('SELECT attempts FROM credential_attempt WHERE bucket=?', (key,)).fetchone()
            if row and row['attempts'] >= limit:
                limited = True
            db.execute('''INSERT INTO credential_attempt VALUES (?,1,?)
                ON CONFLICT(bucket) DO UPDATE SET attempts=attempts+1''', (key, now + 900))
    if limited:
        abort(429, '尝试次数过多，请在 15 分钟后重试')
