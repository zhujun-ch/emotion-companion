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

    def test_delete_missing_session_does_not_leak_lock_and_delete_cleans_lock(self):
        backend.conversation_locks.clear()
        self.assertEqual(self.client.delete('/api/sessions/nonexistent-session').status_code, 404)
        self.assertNotIn('nonexistent-session', backend.conversation_locks)
        session = self.create()
        with patch.object(backend, 'predict_emotion', return_value=('快乐', .8)), patch.object(backend, 'ask_ollama', return_value='在听。'):
            self.assertEqual(self.send(session, '你好').status_code, 200)
        self.assertIn(session, backend.conversation_locks)
        self.assertEqual(self.client.delete(f'/api/sessions/{session}').status_code, 200)
        self.assertNotIn(session, backend.conversation_locks)

    def test_session_messages_preserves_reference_after_feedback(self):
        session = self.create()
        ref = {'version': 2, 'label': '快乐', 'candidates': ['快乐', '中性'], 'turn_count': 4, 'evidence_count': 4, 'state': 'ready', 'reason': 'ok'}
        with patch.object(backend, 'predict_emotion', return_value=('快乐', .9)), \
                patch.object(backend, 'ask_ollama', return_value='在听。'), \
                patch.object(backend.emotion_reference_policy, 'assess', return_value=ref):
            for text in ('一', '二', '三', '四'):
                resp = self.send(session, text)
                self.assertEqual(resp.status_code, 200)
            mid = resp.json['assistant_message_id']
        self.assertEqual(self.client.post(f'/api/messages/{mid}/feedback', json={'agreed': False, 'correction': '悲伤'}).status_code, 200)
        with patch.object(backend.emotion_reference_policy, 'assess', side_effect=AssertionError('should not overwrite feedback snapshot')):
            fetched = self.client.get(f'/api/sessions/{session}/messages')
            self.assertEqual(fetched.status_code, 200)
            self.assertEqual(fetched.json['messages'][-1]['emotion_reference']['label'], '快乐')

    def test_legacy_chat_without_session_cleans_up_empty_session_on_failure(self):
        backend.conversation_locks.clear()
        with patch.object(backend, 'predict_emotion', return_value=('快乐', .8)), \
                patch.object(backend, 'ask_ollama', side_effect=requests.ConnectionError('down')):
            resp = self.client.post('/api/chat', json={'text': '今天有点难过'})
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(self.store.list(self.user), [])
        self.assertEqual(backend.conversation_locks, {})

    def test_standalone_store_initializes_emotion_record_table(self):
        standalone = ConversationStore(Path(self.temp.name) / 'standalone.sqlite3', save_emotion_records=True)
        sid = standalone.create(self.user)['id']
        standalone.save_turn(sid, self.user, '你好', '我在', '中性', .8)
        with standalone.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM emotion_record').fetchone()[0], 1)

    def test_sessions_and_messages_pagination(self):
        s1, s2, s3 = self.create(), self.create(), self.create()
        for idx in range(3):
            self.store.save_turn(s1, self.user, f'u{idx}', f'a{idx}', '快乐', .8)
        self.store.save_turn(s2, self.user, 'u_s2', 'a_s2', '中性', .7)
        self.store.save_turn(s3, self.user, 'u_s3', 'a_s3', '悲伤', .9)

        page1 = self.client.get('/api/sessions?limit=2&offset=0')
        self.assertEqual(page1.status_code, 200)
        self.assertEqual([s['id'] for s in page1.json['sessions']], [s3, s2])
        self.assertTrue(page1.json['has_more'])
        self.assertEqual(page1.json['next_offset'], 2)

        page2 = self.client.get('/api/sessions?limit=2&offset=2')
        self.assertEqual([s['id'] for s in page2.json['sessions']], [s1])
        self.assertFalse(page2.json['has_more'])
        self.assertIsNone(page2.json['next_offset'])
        self.assertEqual(self.client.get('/api/sessions?limit=0').status_code, 400)

        msg_p1 = self.client.get(f'/api/sessions/{s1}/messages?limit=4')
        self.assertEqual(msg_p1.status_code, 200)
        self.assertEqual([m['content'] for m in msg_p1.json['messages']], ['u1', 'a1', 'u2', 'a2'])
        self.assertTrue(msg_p1.json['has_more'])
        before_id = msg_p1.json['next_before_id']

        msg_p2 = self.client.get(f'/api/sessions/{s1}/messages?limit=4&before_id={before_id}')
        self.assertEqual([m['content'] for m in msg_p2.json['messages']], ['u0', 'a0'])
        self.assertFalse(msg_p2.json['has_more'])
        self.assertIsNone(msg_p2.json['next_before_id'])

    def test_request_receipt_ttl_pruning(self):
        import os
        from time import time
        with patch.dict(os.environ, {'REQUEST_RECEIPT_TTL_SECONDS': '120'}):
            first = self.client.post('/api/sessions', json={'request_id': 'ttl-req-0001'})
            self.assertEqual(first.status_code, 201)
            with self.store.connect() as db:
                db.execute("UPDATE request_receipt SET created_at=? WHERE request_id='ttl-req-0001'", (int(time()) - 300,))
            self.assertIsNone(self.store.replay(self.user, 'ttl-req-0001', 'different'))
            second = self.client.post('/api/sessions', json={'request_id': 'ttl-req-0002'})
            self.assertEqual(second.status_code, 201)
            with self.store.connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM request_receipt WHERE request_id='ttl-req-0001'").fetchone()[0], 0)

    def test_emotion_stats_aggregates_sources_and_isolates_users(self):
        from datetime import datetime, timedelta, timezone
        from flask import abort
        with patch.object(backend.account_auth, 'current_user', side_effect=lambda: abort(401)):
            self.assertEqual(self.client.get('/api/emotions/stats').status_code, 401)

        s1 = self.create()
        self.store.save_turn(s1, self.user, '好开心', '太好了', '快乐', .9, None, chat_route='support')
        self.store.save_turn(s1, self.user, '很失落', '抱抱你', '愤怒', .6, {'state': 'ready', 'label': '悲伤'}, chat_route='mixed')
        _, mid_feedback = self.store.save_turn(s1, self.user, '心里发慌', '深呼吸', '中性', .7, {'state': 'ready', 'label': '中性'}, chat_route='support')
        self.store.save_feedback(mid_feedback, self.user, False, '恐惧')
        _, mid_uncertain = self.store.save_turn(s1, self.user, '说不清', '慢慢说', '惊奇', .7, {'state': 'ready', 'label': '惊奇'}, chat_route='support')
        self.store.save_feedback(mid_uncertain, self.user, False, '说不准')
        self.store.save_turn(s1, self.user, '写个排序', '只聊感受', None, None, None, chat_route='off_topic')
        self.store.save_turn(s1, self.user, '复核未过', '先聊聊', None, None, None, chat_route='fallback')

        other_sid = self.store.create('other_user')['id']
        self.store.save_turn(other_sid, 'other_user', '别人的话', '回应', '愤怒', .9)

        _, old_mid = self.store.save_turn(s1, self.user, '百天前的话', '回应', '惊奇', .8, chat_route='support')
        old_ts = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat(timespec='microseconds')
        with self.store.connect() as db:
            db.execute('UPDATE chat_message SET created_at=? WHERE id=?', (old_ts, old_mid))

        resp = self.client.get('/api/emotions/stats?days=90&limit=2')
        self.assertEqual(resp.status_code, 200)
        data = resp.json
        self.assertEqual(data['total'], 3)
        self.assertEqual(data['counts']['快乐'], 1)
        self.assertEqual(data['counts']['悲伤'], 1)
        self.assertEqual(data['counts']['恐惧'], 1)
        self.assertEqual(data['counts']['惊奇'], 0)
        self.assertEqual(len(data['records']), 2)
        self.assertTrue(data['has_more'])
        self.assertEqual([r['source'] for r in data['records']], ['feedback', 'reference'])
        self.assertEqual(sum(sum(d['counts'].values()) for d in data['daily']), 3)

        wider = self.client.get('/api/emotions/stats?days=120&limit=10')
        self.assertEqual(wider.json['total'], 4)
        self.assertEqual(wider.json['counts']['惊奇'], 1)


if __name__ == '__main__':
    unittest.main()
