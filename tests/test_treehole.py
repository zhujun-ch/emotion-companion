from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from flask import Flask
import requests

from demo_pages import create_demo_pages
from treehole_moderation import moderate_treehole


class TreeholeTests(unittest.TestCase):
    def setUp(self):
        workspace = TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.database = Path(workspace.name) / 'test.sqlite3'
        self.client = self.open_database()
        self.author = self.new_author()
        self.other = self.new_author()

    def open_database(self, password='test-password'):
        app = Flask(__name__)
        app.register_blueprint(create_demo_pages(
            self.database, password,
            lambda body: ('published', '自动审核通过') if body == '鼓励测试' else ('pending', '待复核'),
        ))
        return app.test_client()

    def new_author(self):
        token = self.client.post('/api/demo/posts/session').json['token']
        return {'X-Treehole-Token': token}

    def post(self, body):
        response = self.client.post('/api/demo/posts', json={'kind': '鼓励', 'body': body}, headers=self.author)
        self.assertEqual(response.status_code, 200)
        return response.json['id']

    def lists(self, headers):
        return self.client.get('/api/demo/posts', headers=headers).json

    def test_pending_post_is_private_and_author_only(self):
        item_id = self.post('待审测试')
        self.assertIn(item_id, [row['id'] for row in self.lists(self.author)['mine']])
        self.assertNotIn(item_id, [row['id'] for row in self.lists(self.other)['public']])
        self.assertEqual(self.lists(self.other)['mine'], [])
        url = f'/api/demo/posts/{item_id}/withdraw'
        self.assertEqual(self.client.post(url, headers=self.other).status_code, 404)
        self.assertEqual(self.client.post(url, headers=self.author).status_code, 200)

    def test_remove_checks_reviewer_and_records_audit(self):
        item_id = self.post('鼓励测试')
        url = f'/api/demo/review/posts/{item_id}'
        action = {'action': 'remove', 'reason': '测试下架'}
        self.assertIn(item_id, [row['id'] for row in self.lists(self.other)['public']])
        self.assertEqual(self.client.post(url, json=action, headers=self.other).status_code, 403)
        login = self.client.post('/api/demo/review/login', json={'username': 'admin', 'password': 'test-password'})
        reviewer = {'Authorization': 'Bearer ' + login.json['token']}
        self.assertEqual(self.client.post(url, json=action, headers=reviewer).status_code, 200)
        self.assertNotIn(item_id, [row['id'] for row in self.lists(self.other)['public']])
        self.assertEqual(self.lists(self.author)['mine'][0]['state'], 'removed')
        history = self.client.get('/api/demo/review/history', headers=reviewer).json
        self.assertEqual((history[0]['post_id'], history[0]['action'], history[0]['reason']),
                         (item_id, 'remove', '测试下架'))
        self.assertEqual(self.client.post('/api/demo/review/logout', headers=reviewer).status_code, 200)
        self.assertEqual(self.client.get('/api/demo/review/history', headers=reviewer).status_code, 401)

    def test_posts_and_author_survive_restart_and_old_login_expires_on_password_change(self):
        item_id = self.post('鼓励测试')
        login = self.client.post('/api/demo/review/login', json={'username': 'admin', 'password': 'test-password'})
        reviewer = {'Authorization': 'Bearer ' + login.json['token']}

        self.client = self.open_database(password='new-password')
        self.assertIn(item_id, [row['id'] for row in self.lists(self.other)['public']])
        self.assertIn(item_id, [row['id'] for row in self.lists(self.author)['mine']])
        self.assertEqual(self.client.get('/api/demo/review/history', headers=reviewer).status_code, 401)
        login = self.client.post('/api/demo/review/login', json={'username': 'admin', 'password': 'new-password'})
        reviewer = {'Authorization': 'Bearer ' + login.json['token']}
        history = self.client.get('/api/demo/review/history', headers=reviewer).json
        self.assertEqual(history[0]['post_id'], item_id)

    @patch('treehole_moderation.requests.post')
    def test_rule_blocks_without_model_and_timeout_requires_review(self, request):
        self.assertEqual(moderate_treehole('访问 https://example.test', 'http://local', 'qwen')[0], 'blocked')
        request.assert_not_called()
        request.side_effect = requests.Timeout
        self.assertEqual(moderate_treehole('今天有点难受', 'http://local', 'qwen')[0], 'pending')

    @patch('treehole_moderation.requests.post')
    def test_only_valid_moderation_result_can_publish(self, request):
        response = request.return_value
        response.json.return_value = {'message': {'content': '{"decision":"allow","category":"safe"}'}}
        self.assertEqual(moderate_treehole('今天有点难受', 'http://local', 'qwen')[0], 'published')
        response.json.return_value = {'message': {'content': '{"decision":"allow","category":"privacy"}'}}
        self.assertEqual(moderate_treehole('今天有点难受', 'http://local', 'qwen')[0], 'pending')
