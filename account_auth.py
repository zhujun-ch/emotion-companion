"""Shared account credentials for the web and WeChat clients."""
import re
import sqlite3
from hashlib import sha256
from secrets import token_urlsafe
from time import time
from uuid import uuid4
import os

from flask import Blueprint, abort, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash
from deployment_access import initialize_attempts, consume_attempt


class AccountAuth:
    def __init__(self, connect):
        self.connect = connect
        with connect() as db:
            initialize_attempts(db)
            db.executescript("""
                CREATE TABLE IF NOT EXISTS user_account (
                    id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS user_login (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
                    expires_at INTEGER NOT NULL
                );
            """)
            columns = {row['name'] for row in db.execute('PRAGMA table_info(user_login)')}
            for name, declaration in (('id', 'TEXT'), ('created_at', 'INTEGER'), ('device_label', "TEXT NOT NULL DEFAULT '旧版客户端'")):
                if name not in columns:
                    db.execute(f'ALTER TABLE user_login ADD COLUMN {name} {declaration}')
            db.execute('UPDATE user_login SET id=lower(hex(randomblob(16))) WHERE id IS NULL')
            db.execute('UPDATE user_login SET created_at=expires_at-? WHERE created_at IS NULL', (30 * 86400,))
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_user_login_id ON user_login(id)')
        self.ttl = int(os.getenv('ACCOUNT_TOKEN_TTL_SECONDS', str(30 * 86400)))
        if not 300 <= self.ttl <= 30 * 86400:
            raise RuntimeError('账号凭据有效期须在 300 至 2592000 秒之间')

    @staticmethod
    def token_hash():
        scheme, _, token = request.headers.get('Authorization', '').partition(' ')
        if scheme.lower() != 'bearer' or not token or len(token) > 128:
            abort(401, '请先登录心屿账号')
        return sha256(token.encode()).hexdigest()

    def current_user(self):
        with self.connect() as db:
            row = db.execute("""SELECT a.id, a.username FROM user_account a
                JOIN user_login l ON l.user_id = a.id
                WHERE l.token_hash = ? AND l.expires_at > ?""",
                (self.token_hash(), int(time()))).fetchone()
        if row is None:
            abort(401, '登录已过期，请重新登录')
        return dict(row)

    def blueprint(self):
        routes = Blueprint('accounts', __name__, url_prefix='/api/auth')

        @routes.post('/register', defaults={'registering': True})
        @routes.post('/login', defaults={'registering': False})
        def authenticate(registering):
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                abort(400, '请输入账号和密码')
            username = data.get('username')
            password = data.get('password')
            if not isinstance(username, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{3,32}', username.strip()):
                abort(400, '账号须为 3 至 32 位字母、数字、下划线或连字符')
            if not isinstance(password, str) or not 8 <= len(password) <= 128:
                abort(400, '密码须为 8 至 128 个字符')
            username = username.strip().lower()
            consume_attempt(self.connect, 'account', username)
            device = data.get('device_label', '心屿客户端')
            if not isinstance(device, str) or not 1 <= len(device.strip()) <= 64:
                abort(400, '设备名称须为 1 至 64 个字符')
            if registering:
                user_id = uuid4().hex
                password_hash = generate_password_hash(password)
            else:
                with self.connect() as db:
                    row = db.execute('SELECT id, password_hash FROM user_account WHERE username = ?', (username,)).fetchone()
                if row is None or not check_password_hash(row['password_hash'], password):
                    abort(401, '账号或密码错误')
                user_id = row['id']
            token = token_urlsafe(32)
            now = int(time())
            try:
                with self.connect() as db:
                    if registering:
                        db.execute('INSERT INTO user_account(id, username, password_hash) VALUES (?, ?, ?)',
                                   (user_id, username, password_hash))
                    db.execute('DELETE FROM user_login WHERE expires_at <= ?', (now,))
                    # Recheck the password version while issuing the credential:
                    # a concurrent password change must invalidate old logins.
                    if not registering and not db.execute('SELECT 1 FROM user_account WHERE id=? AND password_hash=?',
                                                          (user_id, row['password_hash'])).fetchone():
                        abort(401, '密码已变更，请重新登录')
                    db.execute('INSERT INTO user_login(token_hash,user_id,expires_at,id,created_at,device_label) VALUES (?, ?, ?, ?, ?, ?)',
                               (sha256(token.encode()).hexdigest(), user_id, now + self.ttl, uuid4().hex, now, device.strip()))
            except sqlite3.IntegrityError:
                if registering:
                    abort(409, '该账号已注册')
                raise
            return jsonify(status='success', token=token, expires_at=now + self.ttl,
                           user={'id': user_id, 'username': username}), 201 if registering else 200

        @routes.get('/me')
        def me():
            return jsonify(status='success', user=self.current_user())

        @routes.post('/logout')
        def logout():
            with self.connect() as db:
                db.execute('DELETE FROM user_login WHERE token_hash = ?', (self.token_hash(),))
            return jsonify(status='success')

        @routes.get('/credentials')
        def credentials():
            owner = self.current_user()['id']
            current_hash = self.token_hash()
            with self.connect() as db:
                rows = db.execute('''SELECT id,device_label,created_at,expires_at,token_hash=? AS current
                    FROM user_login WHERE user_id=? AND expires_at>? ORDER BY created_at DESC''',
                    (current_hash, owner, int(time()))).fetchall()
            return jsonify(status='success', credentials=[dict(row) for row in rows])

        @routes.delete('/credentials/<credential_id>')
        def revoke(credential_id):
            owner = self.current_user()['id']
            with self.connect() as db:
                if not db.execute('DELETE FROM user_login WHERE id=? AND user_id=?', (credential_id, owner)).rowcount:
                    abort(404, '登录凭据不存在')
            return jsonify(status='success')

        @routes.post('/logout-all')
        def logout_all():
            owner = self.current_user()['id']
            with self.connect() as db:
                db.execute('DELETE FROM user_login WHERE user_id=?', (owner,))
            return jsonify(status='success')

        @routes.post('/password')
        def change_password():
            owner = self.current_user()['id']
            data = request.get_json(silent=True)
            if not isinstance(data, dict) or not isinstance(data.get('current_password'), str):
                abort(400, '请输入当前密码')
            password = data.get('new_password')
            if not isinstance(password, str) or not 8 <= len(password) <= 128:
                abort(400, '新密码须为 8 至 128 个字符')
            consume_attempt(self.connect, 'password', owner)
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT password_hash FROM user_account WHERE id=?', (owner,)).fetchone()
                if row is None or not check_password_hash(row['password_hash'], data['current_password']):
                    abort(401, '当前密码不正确')
                db.execute('UPDATE user_account SET password_hash=? WHERE id=?', (generate_password_hash(password), owner))
                db.execute('DELETE FROM user_login WHERE user_id=?', (owner,))
            return jsonify(status='success', msg='密码已更新，请在各端重新登录')

        return routes
