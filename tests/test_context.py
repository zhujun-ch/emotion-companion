import json
import tempfile
import unittest
from pathlib import Path
from flask import request
from unittest.mock import patch
import requests
import app as backend
from chat_boundary import classify_message
from conversation_store import ConversationStore


class BoundaryModelTests(unittest.TestCase):
    @patch('chat_boundary.requests.post')
    def test_mixed_excerpt_must_be_a_proper_substring_of_user_text(self, post):
        text = '今天被批评很难受，帮我翻译说明书'
        response = post.return_value
        response.json.return_value = {'message': {'content': '{"decision":"mixed","support_text":"今天被批评很难受"}'}}
        self.assertEqual(classify_message(text, []), ('mixed', '今天被批评很难受'))
        for excerpt in (text, '今天被同事误解', ''):
            response.json.return_value = {'message': {'content': json.dumps({
                'decision': 'mixed', 'support_text': excerpt,
            })}}
            self.assertEqual(classify_message(text, []), ('fallback', text))


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'chat.sqlite3'
        self.store = ConversationStore(self.path)
        self.swap = patch.object(backend, 'conversation_store', self.store)
        self.swap.start()
        support = patch.object(backend, 'classify_message', side_effect=lambda text, history: ('support', text))
        support.start()
        self.addCleanup(support.stop)
        model_check = patch.object(backend, 'review_reply', return_value=True)
        model_check.start()
        self.addCleanup(model_check.stop)
        auth = patch.object(backend.account_auth, 'current_user',
                            side_effect=lambda: {'id': request.headers.get('X-Test-User', 'context_test')})
        auth.start()
        self.addCleanup(auth.stop)
        self.client = backend.app.test_client()
        self.user = 'context_test'

    def tearDown(self):
        self.swap.stop()
        self.temp.cleanup()

    def create(self):
        r = self.client.post('/api/sessions', json={'user_id': self.user})
        self.assertEqual(r.status_code, 201)
        return r.json['session']['id']

    def send(self, session_id, text='继续聊聊'):
        return self.client.post('/api/chat', json={'user_id': self.user, 'session_id': session_id, 'text': text})

    def test_history_is_persistent_and_scoped_to_session(self):
        one, two = self.create(), self.create()
        with patch.object(backend, 'predict_emotion', return_value=('快乐', .8)), patch.object(backend, 'ask_ollama', return_value='我记住了。') as model:
            self.assertEqual(self.send(one, '我的猫叫栗子').status_code, 200)
            self.assertEqual(model.call_args.args[2], [])
            result = self.send(one, '它叫什么？')
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json['context_turns'], 1)
            self.assertEqual(model.call_args.args[2], [{'role':'user','content':'我的猫叫栗子'}, {'role':'assistant','content':'我记住了。'}])
            self.send(two, '你知道我养了什么吗？')
            self.assertEqual(model.call_args.args[2], [])
        restored = ConversationStore(self.path)
        self.assertEqual(len(restored.messages(one)), 4)
        self.assertEqual(len(restored.messages(two)), 2)
        self.assertEqual(self.client.get(f'/api/sessions/{one}/messages', headers={'X-Test-User': 'someone_else'}).status_code, 404)
        self.assertEqual(self.client.get('/api/sessions', headers={'X-Test-User': 'someone_else'}).json['sessions'], [])

    def test_context_keeps_complete_recent_turns_with_a_budget(self):
        session = self.create()
        for i in range(12):
            self.store.save_turn(session, self.user, f'u{i}', f'a{i}', '快乐', .8)
        history = self.store.context(session, max_turns=8, char_budget=500)
        self.assertEqual(len(history), 16)
        self.assertEqual(history[0]['content'], 'u4')
        self.assertEqual(history[-1]['content'], 'a11')
        self.assertEqual(self.store.context(session, char_budget=5), [])
        self.assertEqual(len(self.store.context(session, char_budget=6)), 2)
        self.assertEqual(len(self.store.messages(session)), 24)

    def test_boundary_routes_do_not_leak_rejected_text_into_model_context(self):
        session = self.create()
        with patch.object(backend, 'classify_message', side_effect=[
            ('off_topic', '解释 TCP 三次握手'), ('urgent', '紧急测试文本'),
            ('mixed', '我很烦'), ('support', '我想说说为什么烦'),
        ]) as classify, \
                patch.object(backend, 'ask_ollama', return_value='未通过检查的候选回复') as generate, \
                patch.object(backend, 'review_reply', side_effect=[False, True]) as review:
            off_topic = self.send(session, '解释 TCP 三次握手').json
            self.assertEqual(off_topic['chat_route'], 'off_topic')
            self.assertEqual(off_topic['reply'], backend.FIXED_REPLIES['off_topic'])
            self.assertEqual(self.store.context(session), [])
            self.assertEqual(self.store.user_evidence(session), ([], 0))
            self.assertEqual(self.send(session, '紧急测试文本').json['chat_route'], 'urgent')
            generate.assert_not_called()
            review.assert_not_called()
            self.assertEqual(self.send(session, '我很烦，帮我代写作业').json['chat_route'], 'fallback')
            self.assertEqual(self.send(session, '我想说说为什么烦').json['chat_route'], 'support')
            history = classify.call_args.args[1]
            self.assertNotIn('解释 TCP 三次握手', [row['content'] for row in history])
            self.assertNotIn('未通过检查的候选回复', [row['content'] for row in history])
            self.assertNotIn('我很烦，帮我代写作业', [row['content'] for row in history])
            self.assertEqual(generate.call_args_list[0].args[0], '我很烦')
        messages = self.client.get(f'/api/sessions/{session}/messages').json['messages']
        self.assertIsNone(messages[1]['emotion_reference'])
        self.assertEqual(messages[1]['chat_route'], 'off_topic')

    def test_boundary_timeout_leaves_no_partial_turn(self):
        session = self.create()
        with patch.object(backend, 'classify_message', side_effect=requests.Timeout), \
                patch.object(backend, 'ask_ollama') as generate:
            self.assertEqual(self.send(session).status_code, 502)
            generate.assert_not_called()
        self.assertEqual(self.store.messages(session), [])

    def test_failure_does_not_save_partial_turn_and_busy_returns_conflict(self):
        session = self.create()
        with patch.object(backend, 'predict_emotion', return_value=('快乐', .8)), patch.object(backend, 'ask_ollama', side_effect=requests.ConnectionError('test')):
            self.assertEqual(self.send(session).status_code, 502)
        self.assertEqual(self.store.messages(session), [])
        lock = backend.conversation_locks[session]
        with lock:
            self.assertEqual(self.send(session).status_code, 409)

    def test_record_migration_and_turn_storage_are_atomic(self):
        with self.store.connect() as db:
            db.execute("CREATE TABLE emotion_record (id INTEGER PRIMARY KEY, user_id TEXT,user_text TEXT,emotion_label TEXT,confidence REAL,llm_reply TEXT)")
            db.execute("INSERT INTO emotion_record VALUES (1,'old','existing','快乐',.7,'old reply')")
        mirrored = ConversationStore(self.path, save_emotion_records=True)
        session = mirrored.create(self.user)['id']
        mirrored.save_turn(session, self.user, 'hello', 'reply', '快乐', .9)
        with mirrored.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM emotion_record').fetchone()[0], 2)
        mirrored.delete(session, self.user)
        with mirrored.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM emotion_record').fetchone()[0], 1)
            db.execute("CREATE TRIGGER test_record_failure BEFORE INSERT ON emotion_record BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        session = mirrored.create(self.user)['id']
        import sqlite3
        with self.assertRaises(sqlite3.Error):
            mirrored.save_turn(session, self.user, 'hello', 'reply', '快乐', .9)
        self.assertEqual(mirrored.messages(session), [])

    def test_delete_and_legacy_client(self):
        with patch.object(backend, 'predict_emotion', return_value=('快乐', .8)), patch.object(backend, 'ask_ollama', return_value='在听呢。'):
            r = self.client.post('/api/chat', json={'text':'旧客户端测试', 'user_id':self.user})
        self.assertEqual(r.status_code, 200)
        session = r.json['session_id']
        self.assertEqual(self.client.delete(f'/api/sessions/{session}', headers={'X-Test-User': 'other'}).status_code, 404)
        self.assertEqual(self.client.delete(f'/api/sessions/{session}').status_code, 200)
        self.assertIsNone(self.store.get(session, self.user))
        self.assertEqual(self.store.messages(session), [])

    def test_request_receipt_replays_after_restart_and_rejects_changed_payload(self):
        session = self.create()
        payload = {'session_id': session, 'text': '今天有点累', 'request_id': 'chat-request-001'}
        with patch.object(backend, 'ask_ollama', return_value='我在听。') as generate:
            first = self.client.post('/api/chat', json=payload)
            self.assertEqual(first.status_code, 200)
            with patch.object(backend, 'conversation_store', ConversationStore(self.path)):
                second = self.client.post('/api/chat', json=payload)
            self.assertEqual(first.json, second.json)
            self.assertEqual(generate.call_count, 1)
            self.assertEqual(self.client.post('/api/chat', json=payload | {'text': '不同内容'}).status_code, 409)
        self.assertEqual(len(self.store.messages(session)), 2)
        self.assertEqual(self.client.post('/api/chat', json=payload, headers={'X-Test-User': 'other'}).status_code, 404)

    def test_independent_workers_deduplicate_inside_transaction_and_reject_stale_turn(self):
        from concurrent.futures import ThreadPoolExecutor
        from werkzeug.exceptions import Conflict
        session = self.create()
        def commit(_):
            worker = ConversationStore(self.path)
            return worker.save_turn(session, self.user, '并发请求', '回复', None, None,
                request_id='worker-request-001', content_hash='same', response={'session_id': session}, expected_count=0)
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(commit, range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.store.messages(session)), 2)
        with self.assertRaises(Conflict):
            self.store.save_turn(session, self.user, '过期上下文', '旧回复', None, None,
                request_id='worker-request-002', content_hash='new', response={}, expected_count=0)
        self.assertEqual(len(self.store.messages(session)), 2)

    def test_new_session_request_is_deduplicated(self):
        payload = {'request_id': 'session-request-001'}
        one = self.client.post('/api/sessions', json=payload)
        two = self.client.post('/api/sessions', json=payload)
        self.assertEqual(one.json, two.json)
        self.assertEqual(len(self.store.list(self.user)), 1)


if __name__ == '__main__':
    unittest.main()
