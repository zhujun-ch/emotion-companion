"""Shared fixture data and interactions for the local three-front-end demo."""
from contextlib import contextmanager
from datetime import date, timedelta
from hashlib import sha256
from hmac import digest
from secrets import compare_digest, token_urlsafe
from time import time
import sqlite3

from flask import Blueprint, abort, jsonify, request

MOODS = ('平静', '开心', '低落', '紧张', '生气', '惊喜')
KINDS = ('鼓励', '倾诉')


def create_demo_pages(path, reviewer_password, moderate_post, *, reviewer_username='admin'):
    pages = Blueprint('demo_pages', __name__, url_prefix='/api/demo')

    @contextmanager
    def database():
        db = sqlite3.connect(path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    with database() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS diary (
                id INTEGER PRIMARY KEY, day TEXT NOT NULL,
                mood TEXT NOT NULL, body TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS post (
                id INTEGER PRIMARY KEY, kind TEXT NOT NULL, body TEXT NOT NULL,
                state TEXT NOT NULL, reason TEXT NOT NULL,
                day TEXT NOT NULL, mine INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS demo_seed (id INTEGER PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS post_author (token_hash TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS reviewer_session (
                token_hash TEXT PRIMARY KEY, expires_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS post_audit (
                id INTEGER PRIMARY KEY, post_id INTEGER NOT NULL, actor TEXT NOT NULL,
                action TEXT NOT NULL, state TEXT NOT NULL, reason TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        columns = {row['name'] for row in db.execute('PRAGMA table_info(post)')}
        if 'author' not in columns:
            db.execute('ALTER TABLE post ADD COLUMN author TEXT')
        if db.execute('INSERT OR IGNORE INTO demo_seed VALUES (1)').rowcount:
            today = date.today()
            db.executemany('INSERT INTO diary(day, mood, body) VALUES (?, ?, ?)', [
                (today.isoformat(), '平静', '晚饭后走了一小段路，回来时心里安静了许多。'),
                ((today - timedelta(days=2)).isoformat(), '开心', '和同学一起完成了小组展示。'),
            ])
            db.executemany(
                'INSERT INTO post(kind, body, state, reason, day, mine) VALUES (?, ?, ?, ?, ?, 0)',
                [
                    ('鼓励', '如果今天只完成了一件小事，那一件也值得记下来。', 'published', '演示样例', today.isoformat()),
                    ('倾诉', '每次在课堂上发言都很紧张，想慢慢练习把话说完。', 'published', '演示样例', today.isoformat()),
                    ('倾诉', '大家总在开玩笑，我分不清那句话是不是在针对我。', 'pending', '语境需要复核', today.isoformat()),
                ],
            )

    @pages.errorhandler(400)
    @pages.errorhandler(401)
    @pages.errorhandler(403)
    @pages.errorhandler(404)
    @pages.errorhandler(409)
    def handle_error(error):
        return jsonify(message=error.description), error.code

    def payload():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            abort(400, '请输入有效内容')
        return data

    def body_text(data, limit):
        body = data.get('body')
        if not isinstance(body, str) or not 1 <= len(body.strip()) <= limit:
            abort(400, f'正文须在 1 至 {limit} 字之间')
        return body.strip()

    @pages.get('/diaries')
    def list_diaries():
        with database() as db:
            return jsonify([dict(row) for row in db.execute('SELECT * FROM diary ORDER BY day DESC, id DESC')])

    @pages.route('/diaries', methods=['POST'])
    @pages.route('/diaries/<int:item_id>', methods=['PUT', 'DELETE'])
    def change_diary(item_id=None):
        if request.method == 'DELETE':
            with database() as db:
                if not db.execute('DELETE FROM diary WHERE id = ?', (item_id,)).rowcount:
                    abort(404, '日记已不存在')
            return jsonify(ok=True)

        data = payload()
        try:
            day = date.fromisoformat(data.get('day', '')).isoformat()
        except (TypeError, ValueError):
            abort(400, '请选择日期')
        mood = data.get('mood')
        if mood not in MOODS:
            abort(400, '请选择心情')
        body = body_text(data, 1000)
        with database() as db:
            if item_id is None:
                db.execute('INSERT INTO diary(day, mood, body) VALUES (?, ?, ?)', (day, mood, body))
            elif not db.execute('UPDATE diary SET day = ?, mood = ?, body = ? WHERE id = ?',
                                (day, mood, body, item_id)).rowcount:
                abort(404, '日记已不存在')
        return jsonify(ok=True)

    def hash_token(token):
        return sha256(token.encode()).hexdigest()

    def hash_reviewer_token(token):
        identity = f'{reviewer_username}:{token}'.encode()
        return digest(reviewer_password.encode(), identity, 'sha256').hex()

    def author_for(db):
        token = request.headers.get('X-Treehole-Token', '')
        if not token:
            return None
        digest = hash_token(token)
        if not db.execute('SELECT 1 FROM post_author WHERE token_hash = ?', (digest,)).fetchone():
            abort(401, '投稿会话已失效，请刷新后重试')
        return digest

    def require_author(db):
        author = author_for(db)
        if not author:
            abort(401, '请先建立投稿会话')
        return author

    def audit(db, post_id, actor, action, state, reason):
        db.execute('INSERT INTO post_audit(post_id, actor, action, state, reason) VALUES (?, ?, ?, ?, ?)',
                   (post_id, actor, action, state, reason))

    @pages.post('/posts/session')
    def start_post_session():
        token = token_urlsafe(32)
        with database() as db:
            db.execute('INSERT INTO post_author VALUES (?)', (hash_token(token),))
        return jsonify(token=token)

    @pages.get('/posts')
    def list_posts():
        with database() as db:
            author = author_for(db)
            public = db.execute('''SELECT id, kind, body, day FROM post
                                   WHERE state = 'published' ORDER BY id DESC''')
            mine = db.execute('''SELECT id, kind, body, state, reason, day FROM post
                                 WHERE author = ? ORDER BY id DESC''', (author,))
            return jsonify(public=[dict(row) for row in public], mine=[dict(row) for row in mine])

    @pages.post('/posts')
    def submit_post():
        data = payload()
        kind = data.get('kind')
        if kind not in KINDS:
            abort(400, '请选择投稿类型')
        body = body_text(data, 500)
        with database() as db:
            author = require_author(db)
        state, reason = moderate_post(body)
        with database() as db:
            item_id = db.execute(
                'INSERT INTO post(kind, body, state, reason, day, mine, author) VALUES (?, ?, ?, ?, ?, 1, ?)',
                (kind, body, state, reason, date.today().isoformat(), author),
            ).lastrowid
            audit(db, item_id, '系统', 'auto', state, reason)
        return jsonify(id=item_id, state=state, reason=reason)

    @pages.post('/posts/<int:item_id>/withdraw')
    def withdraw(item_id):
        with database() as db:
            author = require_author(db)
            if not db.execute('SELECT 1 FROM post WHERE id = ? AND author = ?',
                              (item_id, author)).fetchone():
                abort(404, '投稿不存在')
            if not db.execute('''UPDATE post SET state = 'withdrawn', reason = '作者撤回'
                                 WHERE id = ? AND author = ? AND state IN ('pending', 'published')''',
                              (item_id, author)).rowcount:
                abort(409, '稿件状态已变化，请刷新')
            audit(db, item_id, '作者', 'withdraw', 'withdrawn', '作者撤回')
        return jsonify(ok=True)

    @pages.post('/review/login')
    def login():
        data = payload()
        supplied = data.get('password')
        if (data.get('username') != reviewer_username or not isinstance(supplied, str)
                or not compare_digest(supplied.encode(), reviewer_password.encode())):
            abort(401, '账号或口令不正确')
        token = token_urlsafe(32)
        now = time()
        with database() as db:
            db.execute('DELETE FROM reviewer_session WHERE expires_at <= ?', (now,))
            db.execute('INSERT INTO reviewer_session VALUES (?, ?)', (hash_reviewer_token(token), now + 8 * 3600))
        return jsonify(token=token, role='reviewer')

    def require_reviewer(db):
        scheme, _, token = request.headers.get('Authorization', '').partition(' ')
        if scheme.lower() != 'bearer' or not token:
            if author_for(db):
                abort(403, '当前身份没有树洞审核权限')
            abort(401, '请先登录审核台')
        token_hash = hash_reviewer_token(token)
        if not db.execute('SELECT 1 FROM reviewer_session WHERE token_hash = ? AND expires_at > ?',
                          (token_hash, time())).fetchone():
            abort(401, '审核登录已失效，请重新登录')
        return token_hash

    @pages.get('/review/me')
    def reviewer_identity():
        with database() as db:
            require_reviewer(db)
        return jsonify(role='reviewer')

    @pages.post('/review/logout')
    def logout():
        with database() as db:
            digest = require_reviewer(db)
            db.execute('DELETE FROM reviewer_session WHERE token_hash = ?', (digest,))
        return jsonify(ok=True)

    @pages.get('/review/history')
    def review_history():
        with database() as db:
            require_reviewer(db)
            return jsonify([dict(row) for row in db.execute(
                'SELECT * FROM post_audit ORDER BY id DESC LIMIT 100')])

    @pages.get('/review/posts')
    def review_posts():
        with database() as db:
            require_reviewer(db)
            return jsonify([dict(row) for row in db.execute(
                'SELECT id, kind, body, state, reason, day FROM post ORDER BY id DESC')])

    @pages.post('/review/posts/<int:item_id>')
    def review(item_id):
        with database() as db:
            require_reviewer(db)
            data = payload()
            transition = {
                'approve': ('pending', 'published', '人工审核通过'),
                'reject': ('pending', 'rejected', '人工审核驳回'),
                'remove': ('published', 'removed', '管理员下架'),
            }.get(str(data.get('action')))
            if transition is None:
                abort(400, '未知审核操作')
            previous, state, default_reason = transition
            reason = data.get('reason', '')
            if not isinstance(reason, str) or len(reason.strip()) > 120:
                abort(400, '审核原因最多 120 字')
            if state == 'rejected' and not reason.strip():
                abort(400, '请填写驳回原因')
            reason = reason.strip() or default_reason
            if not db.execute('UPDATE post SET state = ?, reason = ? WHERE id = ? AND state = ?',
                              (state, reason, item_id, previous)).rowcount:
                abort(409, '稿件状态已变化，请刷新')
            audit(db, item_id, reviewer_username, data['action'], state, reason)
        return jsonify(ok=True)

    return pages
