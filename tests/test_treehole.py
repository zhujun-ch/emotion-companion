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

    def test_comments_follow_moderation_and_only_published_are_public(self):
        post_id = self.post('鼓励测试')
        url = f'/api/demo/posts/{post_id}/comments'
        approved = self.client.post(url, json={'body': '鼓励测试'}, headers=self.other)
        pending = self.client.post(url, json={'body': '需要复核'}, headers=self.other)
        self.assertEqual((approved.json['state'], pending.json['state']), ('published', 'pending'))
        public = next(row for row in self.lists(self.author)['public'] if row['id'] == post_id)
        self.assertEqual([row['id'] for row in public['comments']], [approved.json['id']])
        self.assertEqual(len(self.lists(self.author)['mine_comments']), 0)
        self.assertEqual(len(self.lists(self.other)['mine_comments']), 2)
        self.assertEqual(self.client.post(url, json={'body': '测试'}).status_code, 401)
        self.assertEqual(self.client.post(url, json={'body': ' '}, headers=self.other).status_code, 400)
        self.assertEqual(self.client.post('/api/demo/posts/9999/comments', json={'body': '鼓励测试'},
                                          headers=self.other).status_code, 404)

        comment_id = pending.json['id']
        review_url = f'/api/demo/review/comments/{comment_id}'
        self.assertEqual(self.client.post(review_url, json={'action': 'approve'}, headers=self.other).status_code, 403)
        login = self.client.post('/api/demo/review/login', json={'username': 'admin', 'password': 'test-password'})
        reviewer = {'Authorization': 'Bearer ' + login.json['token']}
        self.assertEqual(self.client.post(review_url, json={'action': 'approve'}, headers=reviewer).status_code, 200)
        self.assertEqual(len(next(row for row in self.lists(self.author)['public'] if row['id'] == post_id)['comments']), 2)
        self.assertEqual(self.client.post(f'/api/demo/comments/{comment_id}/withdraw', headers=self.author).status_code, 404)
        self.assertEqual(self.client.post(f'/api/demo/comments/{comment_id}/withdraw', headers=self.other).status_code, 200)
        self.assertEqual(len(next(row for row in self.lists(self.author)['public'] if row['id'] == post_id)['comments']), 1)
        history = self.client.get('/api/demo/review/history', headers=reviewer).json
        self.assertTrue(any(row['target_type'] == 'comment' and row['comment_id'] == comment_id
                            and row['action'] == 'withdraw' for row in history))

        self.client = self.open_database()
        self.assertEqual(self.lists(self.other)['mine_comments'][0]['state'], 'withdrawn')
        self.assertEqual(self.client.post(f'/api/demo/review/posts/{post_id}',
                                          json={'action': 'remove'}, headers=reviewer).status_code, 200)
        self.assertNotIn(post_id, [row['id'] for row in self.lists(self.author)['public']])
        self.assertEqual(self.client.post(url, json={'body': '鼓励测试'}, headers=self.other).status_code, 404)

    def test_reviewer_can_reject_or_remove_replies_without_affecting_parent(self):
        post_id = self.post('鼓励测试')
        url = f'/api/demo/posts/{post_id}/comments'
        pending_id = self.client.post(url, json={'body': '需要复核'}, headers=self.other).json['id']
        public_id = self.client.post(url, json={'body': '鼓励测试'}, headers=self.other).json['id']
        login = self.client.post('/api/demo/review/login', json={'username': 'admin', 'password': 'test-password'})
        reviewer = {'Authorization': 'Bearer ' + login.json['token']}
        comments = self.client.get('/api/demo/review/comments', headers=reviewer).json
        self.assertEqual({row['id'] for row in comments}, {pending_id, public_id})
        self.assertEqual(self.client.post(f'/api/demo/review/comments/{pending_id}',
                                          json={'action': 'reject'}, headers=reviewer).status_code, 400)
        self.assertEqual(self.client.post(f'/api/demo/review/comments/{pending_id}',
                                          json={'action': 'reject', 'reason': '测试原因'},
                                          headers=reviewer).status_code, 200)
        self.assertEqual(self.client.post(f'/api/demo/review/comments/{public_id}',
                                          json={'action': 'remove'}, headers=reviewer).status_code, 200)
        parent = next(row for row in self.lists(self.author)['public'] if row['id'] == post_id)
        self.assertEqual(parent['comments'], [])
        self.assertEqual({row['state'] for row in self.lists(self.other)['mine_comments']},
                         {'removed', 'rejected'})

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
