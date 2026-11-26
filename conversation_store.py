"""Persistent local conversations and bounded, complete-turn model context."""
import sqlite3
import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from emotion_model import LABEL_NAMES
from request_dedup import initialize_receipts, receipt, remember


class ConversationStore:
    def __init__(self, path, save_emotion_records=False):
        self.path = Path(path)
        self.save_emotion_records = save_emotion_records
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            initialize_receipts(db)
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
                CREATE TABLE IF NOT EXISTS emotion_feedback (
                    message_id INTEGER PRIMARY KEY REFERENCES chat_message(id) ON DELETE CASCADE,
                    agreed INTEGER NOT NULL, correction TEXT, updated_at TEXT NOT NULL
                );
            """)
            columns = {r['name'] for r in db.execute('PRAGMA table_info(chat_message)')}
            if 'emotion_reference' not in columns:
                db.execute('ALTER TABLE chat_message ADD COLUMN emotion_reference TEXT')
            if 'chat_route' not in columns:
                db.execute("ALTER TABLE chat_message ADD COLUMN chat_route TEXT NOT NULL DEFAULT 'support'")
            if 'model_text' not in columns:
                db.execute('ALTER TABLE chat_message ADD COLUMN model_text TEXT')
            if save_emotion_records:
                db.execute("""CREATE TABLE IF NOT EXISTS emotion_record (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    user_text TEXT NOT NULL,
                    emotion_label TEXT,
                    confidence REAL,
                    llm_reply TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )""")
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

    def create(self, user_id, request_id=None, content_hash=None):
        now = self.now()
        item = dict(id=uuid.uuid4().hex, user_id=user_id, title='新的倾诉', created_at=now, updated_at=now)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if request_id:
                previous = receipt(db, user_id, 'session', request_id, content_hash)
                if previous is not None:
                    return previous
            db.execute('INSERT INTO chat_session VALUES (:id, :user_id, :title, :created_at, :updated_at)', item)
            result = {k: v for k, v in item.items() if k != 'user_id'} | {'message_count': 0}
            return remember(db, user_id, 'session', request_id, content_hash, result) if request_id else result

    def get(self, session_id, user_id):
        with self.connect() as db:
            row = db.execute('SELECT id,title,created_at,updated_at FROM chat_session WHERE id=? AND user_id=?',
                             (session_id, user_id)).fetchone()
        return dict(row) if row else None

    def list(self, user_id):
        items, _ = self.list_page(user_id, limit=None, offset=0)
        return items

    def list_page(self, user_id, limit=50, offset=0):
        sql = '''SELECT s.id,s.title,s.created_at,s.updated_at,
            (SELECT COUNT(*) FROM chat_message m WHERE m.session_id=s.id) AS message_count
            FROM chat_session s WHERE s.user_id=? ORDER BY s.updated_at DESC, s.id DESC'''
        params = [user_id]
        if limit is not None:
            sql += ' LIMIT ? OFFSET ?'
            params.extend([limit + 1, offset])
        with self.connect() as db:
            rows = db.execute(sql, params).fetchall()
        has_more = limit is not None and len(rows) > limit
        items = [dict(r) for r in (rows[:limit] if limit is not None else rows)]
        return items, has_more

    def messages(self, session_id):
        items, _, _ = self.messages_page(session_id, limit=None, before_id=None)
        return items

    def messages_page(self, session_id, limit=100, before_id=None):
        with self.connect() as db:
            if limit is None:
                rows = db.execute(
                    'SELECT id,session_id,role,content,emotion,confidence,created_at,emotion_reference,chat_route '
                    'FROM chat_message WHERE session_id=? ORDER BY id',
                    (session_id,),
                ).fetchall()
                has_more = False
                page_rows = rows
            else:
                where = 'WHERE session_id=?'
                params = [session_id]
                if before_id is not None:
                    where += ' AND id<?'
                    params.append(before_id)
                params.append(limit + 1)
                rows = db.execute(
                    f'SELECT id,session_id,role,content,emotion,confidence,created_at,emotion_reference,chat_route '
                    f'FROM chat_message {where} ORDER BY id DESC LIMIT ?',
                    params,
                ).fetchall()
                has_more = len(rows) > limit
                page_rows = list(reversed(rows[:limit]))
            ids = [r['id'] for r in page_rows]
            feedback = {}
            if ids:
                placeholders = ','.join('?' for _ in ids)
                feedback = {
                    r['message_id']: dict(r)
                    for r in db.execute(f'SELECT * FROM emotion_feedback WHERE message_id IN ({placeholders})', ids)
                }
        result = []
        for r in page_rows:
            item = dict(r)
            item['emotion_reference'] = json.loads(item['emotion_reference']) if item['emotion_reference'] else None
            item['feedback'] = feedback.get(item['id'])
            result.append(item)
        next_before_id = result[0]['id'] if has_more and result else None
        return result, has_more, next_before_id

    def user_evidence(self, session_id, limit=4):
        with self.connect() as db:
            rows = db.execute("SELECT COALESCE(model_text, content) AS content FROM chat_message WHERE session_id=? AND role='user' AND chat_route IN ('support', 'mixed') ORDER BY id DESC LIMIT ?", (session_id,limit)).fetchall()
            count = db.execute("SELECT COUNT(*) FROM chat_message WHERE session_id=? AND role='user' AND chat_route IN ('support', 'mixed')", (session_id,)).fetchone()[0]
        return [r['content'] for r in reversed(rows)], count

    def save_feedback(self, message_id, user_id, agreed, correction):
        with self.connect() as db:
            row = db.execute('''SELECT m.emotion_reference FROM chat_message m JOIN chat_session s ON s.id=m.session_id
                WHERE m.id=? AND s.user_id=? AND m.role='assistant' ''', (message_id,user_id)).fetchone()
            if not row or not row['emotion_reference']:
                raise LookupError('No reference to correct')
            reference = json.loads(row['emotion_reference'])
            if reference.get('state') != 'ready' and not reference.get('candidates'):
                raise LookupError('No reference to correct')
            db.execute('''INSERT INTO emotion_feedback(message_id,agreed,correction,updated_at) VALUES (?,?,?,?)
                ON CONFLICT(message_id) DO UPDATE SET agreed=excluded.agreed,correction=excluded.correction,updated_at=excluded.updated_at''',
                (message_id,int(agreed),correction,self.now()))
        return {'agreed':agreed,'correction':correction}

    def context(self, session_id, max_turns=8, char_budget=2400):
        with self.connect() as db:
            rows = db.execute("""SELECT role, COALESCE(model_text, content) AS content
                FROM chat_message WHERE session_id=? AND chat_route NOT IN ('off_topic', 'fallback')
                ORDER BY id DESC LIMIT ?""",
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

    def replay(self, user_id, request_id, content_hash):
        with self.connect() as db:
            return receipt(db, user_id, 'chat', request_id, content_hash)

    def save_turn(self, session_id, user_id, text, reply, emotion, confidence, emotion_reference=None, *, chat_route='support', model_text=None,
                  request_id=None, content_hash=None, response=None, expected_count=None):
        now = self.now()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if request_id:
                previous = receipt(db, user_id, 'chat', request_id, content_hash)
                if previous is not None:
                    return previous
            row = db.execute('SELECT title FROM chat_session WHERE id=? AND user_id=?', (session_id, user_id)).fetchone()
            if row is None:
                raise LookupError('Conversation no longer exists')
            count = db.execute('SELECT COUNT(*) FROM chat_message WHERE session_id=?', (session_id,)).fetchone()[0]
            if expected_count is not None and expected_count != count:
                from flask import abort
                abort(409, '对话已有新消息，请刷新后重试')
            user_message = db.execute('INSERT INTO chat_message(session_id,role,content,created_at,chat_route,model_text) VALUES (?, ?, ?, ?, ?, ?)',
                                      (session_id, 'user', text, now, chat_route, model_text))
            assistant_message = db.execute('''INSERT INTO chat_message(session_id,role,content,emotion,confidence,created_at,emotion_reference,chat_route)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (session_id, 'assistant', reply, emotion, confidence, now,
                json.dumps(emotion_reference,ensure_ascii=False) if emotion_reference is not None else None, chat_route))
            title = text[:24] + ('…' if len(text) > 24 else '') if count == 0 else row['title']
            db.execute('UPDATE chat_session SET title=?,updated_at=? WHERE id=?', (title, now, session_id))
            if self.save_emotion_records and chat_route in ('support', 'mixed'):
                db.execute('''INSERT INTO emotion_record(user_id,user_text,emotion_label,confidence,llm_reply,session_id)
                    VALUES (?,?,?,?,?,?)''', (user_id, text, emotion, confidence, reply, session_id))
            if request_id:
                result = response | {'user_message_id': user_message.lastrowid,
                                     'assistant_message_id': assistant_message.lastrowid}
                return remember(db, user_id, 'chat', request_id, content_hash, result)
            return user_message.lastrowid, assistant_message.lastrowid

    def emotion_stats(self, user_id, days=90, detail_limit=200):
        beijing_tz = timezone(timedelta(hours=8))
        today_bj = datetime.now(beijing_tz).date()
        start_day_bj = today_bj - timedelta(days=days - 1)
        first_day = start_day_bj.isoformat()
        last_day = today_bj.isoformat()
        utc_lower = datetime.combine(start_day_bj, datetime.min.time(), tzinfo=beijing_tz).astimezone(timezone.utc).isoformat(timespec='microseconds')
        with self.connect() as db:
            rows = db.execute('''SELECT a.id, a.session_id, s.title AS session_title, a.emotion, a.confidence,
                a.emotion_reference, a.created_at, f.agreed, f.correction,
                (SELECT u.content FROM chat_message u
                 WHERE u.session_id=a.session_id AND u.role='user' AND u.id<a.id
                 ORDER BY u.id DESC LIMIT 1) AS user_text
                FROM chat_message a
                JOIN chat_session s ON s.id=a.session_id
                LEFT JOIN emotion_feedback f ON f.message_id=a.id
                WHERE s.user_id=? AND a.role='assistant' AND a.chat_route IN ('support', 'mixed')
                  AND a.created_at>=?
                ORDER BY a.id DESC''', (user_id, utc_lower)).fetchall()
        counts = {label: 0 for label in LABEL_NAMES}
        daily_map = {}
        records = []
        total = 0
        for row in rows:
            if row['agreed'] == 0:
                if row['correction'] in LABEL_NAMES:
                    emotion, source = row['correction'], 'feedback'
                else:
                    continue
            else:
                ref = json.loads(row['emotion_reference']) if row['emotion_reference'] else None
                if ref and ref.get('state') == 'ready' and ref.get('label') in LABEL_NAMES:
                    emotion, source = ref['label'], 'reference'
                elif row['emotion'] in LABEL_NAMES:
                    emotion, source = row['emotion'], 'model'
                else:
                    continue
            dt = datetime.fromisoformat(row['created_at'])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            day = dt.astimezone(beijing_tz).date().isoformat()
            if not (first_day <= day <= last_day):
                continue
            total += 1
            counts[emotion] += 1
            day_counts = daily_map.setdefault(day, {})
            day_counts[emotion] = day_counts.get(emotion, 0) + 1
            if len(records) < detail_limit:
                records.append({
                    'id': row['id'],
                    'session_id': row['session_id'],
                    'session_title': row['session_title'],
                    'day': day,
                    'created_at': row['created_at'],
                    'emotion': emotion,
                    'source': source,
                    'confidence': row['confidence'],
                    'text': row['user_text'] or '',
                })
        return {
            'days': days,
            'labels': list(LABEL_NAMES),
            'total': total,
            'counts': counts,
            'daily': [{'day': day, 'counts': daily_map[day]} for day in sorted(daily_map)],
            'records': records,
            'has_more': total > len(records),
        }

    def delete(self, session_id, user_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            deleted = db.execute('DELETE FROM chat_session WHERE id=? AND user_id=?', (session_id, user_id)).rowcount
            if deleted:
                db.execute('''DELETE FROM request_receipt WHERE user_id=? AND
                    ((scope='chat' AND json_extract(response, '$.session_id')=?) OR
                     (scope='session' AND json_extract(response, '$.id')=?))''', (user_id, session_id, session_id))
            if deleted and self.save_emotion_records:
                db.execute('DELETE FROM emotion_record WHERE session_id=?', (session_id,))
        return bool(deleted)
