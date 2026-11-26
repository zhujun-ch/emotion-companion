import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from flask import Flask, jsonify
from account_auth import AccountAuth
from conversation_store import ConversationStore
from deployment_access import configure_access


class AccessTests(unittest.TestCase):
    def app(self):
        app = Flask(__name__)
        configure_access(app)
        app.add_url_rule('/api/ping', view_func=lambda: jsonify(ok=True))
        app.add_url_rule('/api/demo/review/posts', endpoint='review', view_func=lambda: jsonify(ok=True))
        return app.test_client()

    @patch.dict(os.environ, {}, clear=True)
    def test_origins_hosts_and_reviewer_network_are_enforced(self):
        client = self.app()
        approved = client.get('/api/ping', headers={'Origin': 'http://127.0.0.1:5173'})
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.headers['Access-Control-Allow-Origin'], 'http://127.0.0.1:5173')
        self.assertEqual(approved.headers['Cache-Control'], 'no-store')
        self.assertEqual(client.get('/api/ping', headers={'Origin': 'https://untrusted.test'}).status_code, 403)
        self.assertEqual(client.get('/api/ping', base_url='http://untrusted.test').status_code, 400)
        self.assertEqual(client.get('/api/demo/review/posts', environ_overrides={'REMOTE_ADDR': '192.168.1.15'},
                                   headers={'X-Forwarded-For': '127.0.0.1'}).status_code, 403)
        self.assertEqual(client.get('/api/demo/review/posts').status_code, 200)
        preflight = client.options('/api/ping', headers={'Origin': 'http://127.0.0.1:5173',
            'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'Authorization,X-Request-ID'})
        self.assertIn('X-Request-ID', preflight.headers['Access-Control-Allow-Headers'])

    @patch.dict(os.environ, {'APP_ENV': 'production'}, clear=True)
    def test_production_fails_closed_without_explicit_configuration(self):
        with self.assertRaises(RuntimeError):
            self.app()
        config = {'APP_ALLOWED_ORIGINS': 'https://emotion.example.test',
                  'APP_TRUSTED_HOSTS': 'emotion.example.test',
                  'REVIEWER_ALLOWED_NETWORKS': '127.0.0.1/32', 'ENABLE_DEMO_PAGES': '1',
                  'DEMO_REVIEWER_PASSWORD': 'plaintext'}
        with patch.dict(os.environ, config):
            with self.assertRaises(RuntimeError):
                self.app()
        config.pop('DEMO_REVIEWER_PASSWORD')
        config['DEMO_REVIEWER_PASSWORD_HASH'] = 'scrypt:32768:8:1$placeholder$placeholder'
        with patch.dict(os.environ, config):
            client = self.app()
            self.assertEqual(client.get('/api/ping', base_url='https://emotion.example.test').status_code, 200)

    def test_production_loopback_proxy_does_not_trigger_global_ip_lockout(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'APP_ENV': 'production'}):
            store = ConversationStore(Path(directory) / 'auth.sqlite3')
            app = Flask(__name__)
            app.register_blueprint(AccountAuth(store.connect).blueprint())
            client = app.test_client()
            for index in range(45):
                response = client.post(
                    '/api/auth/login',
                    json={'username': f'user_{index}', 'password': 'wrong-password'},
                    environ_overrides={'REMOTE_ADDR': '127.0.0.1'},
                )
                self.assertEqual(response.status_code, 401)
            for _ in range(10):
                response = client.post(
                    '/api/auth/login',
                    json={'username': 'target_user', 'password': 'wrong-password'},
                    environ_overrides={'REMOTE_ADDR': '127.0.0.1'},
                )
                self.assertEqual(response.status_code, 401)
            blocked = client.post(
                '/api/auth/login',
                json={'username': 'target_user', 'password': 'wrong-password'},
                environ_overrides={'REMOTE_ADDR': '127.0.0.1'},
            )
            self.assertEqual(blocked.status_code, 429)
