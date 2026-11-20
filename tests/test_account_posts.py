import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from contextlib import contextmanager

from flask import Flask

from account_auth import AccountAuth
from conversation_store import ConversationStore
from demo_pages import create_demo_pages


class AccountPostTests(unittest.TestCase):
    @contextmanager
    def database(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'pages.sqlite3'
        store = ConversationStore(Path(directory.name) / 'accounts.sqlite3')
        auth = AccountAuth(store.connect)
        self.app = Flask(__name__)
        self.app.register_blueprint(auth.blueprint())
        self.moderate = lambda body: ('pending' if body == '待审核' else 'published', '测试审核')
        self.app.register_blueprint(create_demo_pages(
            self.path, 'test-password', lambda body: self.moderate(body),
            diary_owner=lambda: auth.current_user()['id']))
        self.client = self.app.test_client()
        self.credentials = {'username': 'shared_owner', 'password': 'test-password'}
        registered = self.client.post('/api/auth/register', json=self.credentials).json
        self.owner = registered['user']['id']
        self.web = {'Authorization': 'Bearer ' + registered['token']}
        login = self.client.post('/api/auth/login', json=self.credentials).json
        self.mini = {'Authorization': 'Bearer ' + login['token']}
        stranger = self.client.post('/api/auth/register', json=self.credentials | {'username': 'stranger'}).json
        self.other = {'Authorization': 'Bearer ' + stranger['token']}

    def post(self, body='测试匿名投稿', request_id='post-request-001'):
        return self.client.post('/api/demo/posts', json={'kind': '倾诉', 'body': body, 'request_id': request_id}, headers=self.web)

    def test_cross_device_ownership_is_private_and_public_remains_anonymous(self):
        post_id = self.post().json['id']
        pending_id = self.post('待审核', 'post-request-002').json['id']
        comment = self.client.post(f'/api/demo/posts/{post_id}/comments', headers=self.web,
                                   json={'body': '匿名回复', 'request_id': 'comment-request-001'}).json
        mine = self.client.get('/api/demo/posts', headers=self.mini).json
        self.assertEqual({r['id'] for r in mine['mine']}, {post_id, pending_id})
        self.assertEqual(mine['mine_comments'][0]['id'], comment['id'])
        for headers in ({}, self.other):
            response = self.client.get('/api/demo/posts', headers=headers).json
            self.assertEqual(response['mine'], [])
            self.assertEqual(response['mine_comments'], [])
            self.assertNotIn(pending_id, [r['id'] for r in response['public']])
            public = next(r for r in response['public'] if r['id'] == post_id)
            self.assertEqual(set(public), {'id', 'kind', 'body', 'day', 'comments'})
            self.assertFalse({'user_id', 'author', 'username', 'token'} & set(public['comments'][0]))
        self.assertEqual(self.client.post(f'/api/demo/posts/{post_id}/withdraw', headers=self.other).status_code, 404)
        self.assertEqual(self.client.post(f'/api/demo/posts/{post_id}/withdraw', headers=self.mini).status_code, 200)
        self.assertEqual(self.client.post('/api/demo/posts', json={'kind': '鼓励', 'body': '匿名写入'}).status_code, 401)

    def test_legacy_claim_is_atomic_and_cannot_be_reassigned(self):
        token = 'legacy-device-token'
        digest = sha256(token.encode()).hexdigest()
        with self.database() as db:
            db.execute('INSERT INTO post_author(token_hash) VALUES (?)', (digest,))
            post_id = db.execute("INSERT INTO post(kind,body,state,reason,day,mine,author) VALUES ('倾诉','旧稿','published','','2026-11-20',1,?)", (digest,)).lastrowid
            db.execute("INSERT INTO post_comment(post_id,body,state,reason,day,author) VALUES (?,'旧回复','pending','','2026-11-20',?)", (post_id, digest))
        claim = self.web | {'X-Treehole-Token': token}
        result = self.client.post('/api/demo/posts/claim', headers=claim)
        self.assertEqual(result.json, {'ok': True, 'posts': 1, 'comments': 1})
        self.assertEqual(self.client.post('/api/demo/posts/claim', headers=claim).json['posts'], 0)
        self.assertEqual(self.client.post('/api/demo/posts/claim', headers=self.other | {'X-Treehole-Token': token}).status_code, 409)
        mine = self.client.get('/api/demo/posts', headers=self.mini).json
        self.assertEqual(mine['mine'][0]['id'], post_id)
        self.assertEqual(len(mine['mine_comments']), 1)
        self.assertEqual(self.client.get('/api/demo/posts', headers={'X-Treehole-Token': token}).json['mine'], [])
        self.assertEqual(self.client.post(f'/api/demo/posts/{post_id}/withdraw', headers={'X-Treehole-Token': token}).status_code, 401)

    def test_parallel_post_retries_commit_one_post_and_one_audit(self):
        barrier = Barrier(2)
        def moderate(body):
            barrier.wait(timeout=5)
            return 'published', '通过'
        self.moderate = moderate
        def send(_):
            with self.app.test_client() as client:
                return client.post('/api/demo/posts', headers=self.web,
                    json={'kind': '鼓励', 'body': '并发测试', 'request_id': 'parallel-request-001'})
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(send, range(2)))
        self.assertEqual([r.status_code for r in results], [200, 200])
        self.assertEqual(results[0].json, results[1].json)
        with self.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM post WHERE user_id=?', (self.owner,)).fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM post_audit').fetchone()[0], 1)
        self.assertEqual(self.post('不同内容', 'parallel-request-001').status_code, 409)

    def test_comment_diary_and_receipt_rollback(self):
        post_id = self.post().json['id']
        path = f'/api/demo/posts/{post_id}/comments'
        payload = {'body': '回复去重', 'request_id': 'comment-request-001'}
        one = self.client.post(path, headers=self.web, json=payload)
        two = self.client.post(path, headers=self.mini, json=payload)
        self.assertEqual(one.json, two.json)
        self.assertEqual(self.client.post(path, headers=self.web, json=payload | {'body': '修改'}).status_code, 409)
        diary = {'day': '2026-11-20', 'mood': '平静', 'body': '日记去重', 'request_id': 'diary-request-001'}
        for _ in range(2):
            self.assertEqual(self.client.post('/api/demo/diaries', headers=self.web, json=diary).status_code, 200)
        self.assertEqual(len(self.client.get('/api/demo/diaries', headers=self.mini).json), 1)
        with self.database() as db:
            db.execute("CREATE TRIGGER failed_audit BEFORE INSERT ON post_audit BEGIN SELECT RAISE(ABORT, 'test'); END")
        self.app.config['TESTING'] = True
        with self.assertRaises(sqlite3.IntegrityError):
            self.post('回滚', 'rollback-request-001')
        with self.database() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM post WHERE body='回滚'").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM request_receipt WHERE request_id='rollback-request-001'").fetchone()[0], 0)
