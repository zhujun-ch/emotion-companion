import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import requests
import app as backend
from conversation_store import ConversationStore


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'chat.sqlite3'
        self.store = ConversationStore(self.path)
        self.swap = patch.object(backend, 'conversation_store', self.store)
        self.swap.start()
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
        self.assertEqual(self.client.get(f'/api/sessions/{one}/messages?user_id=someone_else').status_code, 404)
        self.assertEqual(self.client.get('/api/sessions?user_id=someone_else').json['sessions'], [])

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
        self.assertEqual(self.client.delete(f'/api/sessions/{session}?user_id=other').status_code, 404)
        self.assertEqual(self.client.delete(f'/api/sessions/{session}?user_id={self.user}').status_code, 200)
        self.assertIsNone(self.store.get(session, self.user))
        self.assertEqual(self.store.messages(session), [])


if __name__ == '__main__':
    unittest.main()
