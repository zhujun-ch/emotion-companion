"""Persistent local conversations and bounded, complete-turn model context."""
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class ConversationStore:
    def __init__(self, path, save_emotion_records=False):
        self.path = Path(path)
        self.save_emotion_records = save_emotion_records
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS chat_session (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chat_message (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES chat_session(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL, emotion TEXT, confidence REAL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_chat_session_user ON chat_session(user_id, updated_at);
                CREATE INDEX IF NOT EXISTS idx_chat_message_session ON chat_message(session_id, id);
            """)
            if save_emotion_records:
                columns = {r['name'] for r in db.execute('PRAGMA table_info(emotion_record)')}
                if 'session_id' not in columns:
                    db.execute('ALTER TABLE emotion_record ADD COLUMN session_id TEXT')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat(timespec='microseconds')

    def create(self, user_id):
        now = self.now()
        item = dict(id=uuid.uuid4().hex, user_id=user_id, title='新的倾诉', created_at=now, updated_at=now)
        with self.connect() as db:
            db.execute('INSERT INTO chat_session VALUES (:id, :user_id, :title, :created_at, :updated_at)', item)
        return {k: v for k, v in item.items() if k != 'user_id'} | {'message_count': 0}

    def get(self, session_id, user_id):
        with self.connect() as db:
            row = db.execute('SELECT id,title,created_at,updated_at FROM chat_session WHERE id=? AND user_id=?',
                             (session_id, user_id)).fetchone()
        return dict(row) if row else None

    def list(self, user_id):
        with self.connect() as db:
            rows = db.execute('''SELECT s.id,s.title,s.created_at,s.updated_at,
                (SELECT COUNT(*) FROM chat_message m WHERE m.session_id=s.id) AS message_count
                FROM chat_session s WHERE s.user_id=? ORDER BY s.updated_at DESC''', (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def messages(self, session_id):
        with self.connect() as db:
            rows = db.execute('SELECT * FROM chat_message WHERE session_id=? ORDER BY id', (session_id,)).fetchall()
        return [dict(r) for r in rows]

    def context(self, session_id, max_turns=8, char_budget=2400):
        with self.connect() as db:
            rows = db.execute('SELECT role,content FROM chat_message WHERE session_id=? ORDER BY id DESC LIMIT ?',
                              (session_id, max_turns * 2)).fetchall()
        history = [dict(r) for r in reversed(rows)]
        selected = []
        for end in range(len(history), 1, -2):
            pair = history[end - 2:end]
            if [m['role'] for m in pair] != ['user', 'assistant']:
                break
            size = sum(len(m['content']) for m in pair)
            if size > char_budget:
                break
            char_budget -= size
            selected = pair + selected
        return selected

    def save_turn(self, session_id, user_id, text, reply, emotion, confidence):
        now = self.now()
        with self.connect() as db:
            row = db.execute('SELECT title FROM chat_session WHERE id=? AND user_id=?', (session_id, user_id)).fetchone()
            if row is None:
                raise LookupError('Conversation no longer exists')
            count = db.execute('SELECT COUNT(*) FROM chat_message WHERE session_id=?', (session_id,)).fetchone()[0]
            user_message = db.execute('INSERT INTO chat_message(session_id,role,content,created_at) VALUES (?, ?, ?, ?)',
                                      (session_id, 'user', text, now))
            assistant_message = db.execute('''INSERT INTO chat_message(session_id,role,content,emotion,confidence,created_at)
                VALUES (?, ?, ?, ?, ?, ?)''', (session_id, 'assistant', reply, emotion, confidence, now))
            title = text[:24] + ('…' if len(text) > 24 else '') if count == 0 else row['title']
            db.execute('UPDATE chat_session SET title=?,updated_at=? WHERE id=?', (title, now, session_id))
            if self.save_emotion_records:
                db.execute('''INSERT INTO emotion_record(user_id,user_text,emotion_label,confidence,llm_reply,session_id)
                    VALUES (?,?,?,?,?,?)''', (user_id, text, emotion, confidence, reply, session_id))
            return user_message.lastrowid, assistant_message.lastrowid

    def delete(self, session_id, user_id):
        with self.connect() as db:
            deleted = db.execute('DELETE FROM chat_session WHERE id=? AND user_id=?', (session_id, user_id)).rowcount
            if deleted and self.save_emotion_records:
                db.execute('DELETE FROM emotion_record WHERE session_id=?', (session_id,))
        return bool(deleted)
