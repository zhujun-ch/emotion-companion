from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import app as backend
from account_auth import AccountAuth
from conversation_store import ConversationStore


class AccountTests(unittest.TestCase):
    def test_independent_logins_share_history_without_trusting_user_id(self):
        with TemporaryDirectory() as directory:
            store = ConversationStore(Path(directory) / 'chat.sqlite3')
            AccountAuth(store.connect)
            with patch.object(backend, 'conversation_store', store), patch.object(backend.account_auth, 'connect', store.connect):
                web, mini, other = (backend.app.test_client() for _ in range(3))
                credentials = {'username': 'shared_user', 'password': 'test-password'}
                registration = web.post('/api/auth/register', json=credentials)
                self.assertEqual(registration.status_code, 201)
                self.assertEqual(web.post('/api/auth/register', json=credentials).status_code, 409)
                self.assertEqual(mini.post('/api/auth/login', json=credentials | {'password': 'incorrect'}).status_code, 401)
                login = mini.post('/api/auth/login', json=credentials)
                stranger = other.post('/api/auth/register', json=credentials | {'username': 'other_user'})
                owner = registration.json['user']['id']
                self.assertEqual(login.json['user']['id'], owner)
                self.assertNotEqual(registration.json['token'], login.json['token'])
                web_headers, mini_headers, other_headers = (
                    {'Authorization': 'Bearer ' + response.json['token']}
                    for response in (registration, login, stranger)
                )
                session = web.post('/api/sessions', headers=web_headers, json={}).json['session']
                store.save_turn(session['id'], owner, '测试倾诉', '测试回复', '中性', .8)
                path = f"/api/sessions/{session['id']}/messages"
                self.assertEqual(mini.get(path, headers=mini_headers).json['messages'][1]['content'], '测试回复')
                self.assertEqual(other.get(path, query_string={'user_id': owner}, headers=other_headers).status_code, 404)
                self.assertEqual(other.get(path, query_string={'user_id': owner}).status_code, 401)
                self.assertEqual(web.post('/api/auth/logout', headers=web_headers).status_code, 200)
                self.assertEqual(web.get(path, headers=web_headers).status_code, 401)
                self.assertEqual(mini.get(path, headers=mini_headers).status_code, 200)


class CredentialTests(unittest.TestCase):
    def setUp(self):
        workspace = TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.store = ConversationStore(Path(workspace.name) / 'accounts.sqlite3')
        from flask import Flask
        self.app = Flask(__name__)
        self.app.register_blueprint(AccountAuth(self.store.connect).blueprint())
        self.client = self.app.test_client()
        self.password = {'username': 'credential_user', 'password': 'test-password'}
        self.web_result = self.client.post('/api/auth/register', json=self.password | {'device_label': '网页'}).json
        self.mini_result = self.client.post('/api/auth/login', json=self.password | {'device_label': '微信'}).json
        self.web = {'Authorization': 'Bearer ' + self.web_result['token']}
        self.mini = {'Authorization': 'Bearer ' + self.mini_result['token']}

    def test_list_revoke_and_logout_all(self):
        credentials = self.client.get('/api/auth/credentials', headers=self.web).json['credentials']
        self.assertEqual(len(credentials), 2)
        self.assertEqual(sum(row['current'] for row in credentials), 1)
        self.assertTrue(all('token_hash' not in row and 'token' not in row for row in credentials))
        target = next(row['id'] for row in credentials if not row['current'])
        other = self.client.post('/api/auth/register', json=self.password | {'username': 'other_user'}).json
        stranger = {'Authorization': 'Bearer ' + other['token']}
        self.assertEqual(self.client.delete('/api/auth/credentials/' + target, headers=stranger).status_code, 404)
        self.assertEqual(self.client.delete('/api/auth/credentials/' + target, headers=self.web).status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me', headers=self.mini).status_code, 401)
        self.assertEqual(self.client.get('/api/auth/me', headers=self.web).status_code, 200)
        self.assertEqual(self.client.post('/api/auth/logout-all', headers=self.web).status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me', headers=self.web).status_code, 401)

    def test_password_change_revokes_every_credential_and_expiry_is_enforced(self):
        payload = {'current_password': 'incorrect', 'new_password': 'new-password'}
        self.assertEqual(self.client.post('/api/auth/password', headers=self.web, json=payload).status_code, 401)
        self.assertEqual(self.client.post('/api/auth/password', headers=self.web,
            json=payload | {'current_password': self.password['password']}).status_code, 200)
        for headers in (self.web, self.mini):
            self.assertEqual(self.client.get('/api/auth/me', headers=headers).status_code, 401)
        self.assertEqual(self.client.post('/api/auth/login', json=self.password).status_code, 401)
        new = self.client.post('/api/auth/login', json=self.password | {'password': 'new-password'}).json
        headers = {'Authorization': 'Bearer ' + new['token']}
        with self.store.connect() as db:
            db.execute('UPDATE user_login SET expires_at=0')
        self.assertEqual(self.client.get('/api/auth/me', headers=headers).status_code, 401)

    def test_failed_logins_are_limited_and_no_raw_credentials_are_stored(self):
        for _ in range(8):
            self.assertEqual(self.client.post('/api/auth/login', json=self.password | {'password': 'incorrect'}).status_code, 401)
        self.assertEqual(self.client.post('/api/auth/login', json=self.password).status_code, 429)
        with self.store.connect() as db:
            rows = db.execute('SELECT * FROM user_login').fetchall()
            self.assertTrue(all(row['token_hash'] != self.web_result['token'] for row in rows))
            stored = db.execute('SELECT password_hash FROM user_account').fetchone()[0]
            self.assertNotEqual(stored, self.password['password'])
