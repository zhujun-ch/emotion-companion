"""Shared fixture data and interactions for the local three-front-end demo."""
from contextlib import contextmanager
from datetime import date, timedelta
from secrets import compare_digest, token_urlsafe
import re
import sqlite3

from flask import Blueprint, abort, jsonify, request

MOODS = ('平静', '开心', '低落', '紧张', '生气', '惊喜')
KINDS = ('鼓励', '倾诉')


def create_demo_pages(path, reviewer_password):
    pages = Blueprint('demo_pages', __name__, url_prefix='/api/demo')
    reviewer_token = token_urlsafe(32)

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
        """)
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

    @pages.get('/posts')
    def list_posts():
        with database() as db:
            public = db.execute("""SELECT id, kind, body, day FROM post
                                   WHERE state = 'published' ORDER BY id DESC""")
            mine = db.execute("""SELECT id, kind, body, state, reason, day FROM post
                                 WHERE mine = 1 ORDER BY id DESC""")
            return jsonify(public=[dict(row) for row in public], mine=[dict(row) for row in mine])

    @pages.post('/posts')
    def submit_post():
        data = payload()
        kind = data.get('kind')
        if kind not in KINDS:
            abort(400, '请选择投稿类型')
        body = body_text(data, 500)
        if re.search(r'https?://|1[3-9][0-9]{9}', body, re.IGNORECASE):
            state, reason = 'blocked', '检测到链接或联系方式'
        else:
            state, reason = 'pending', '演示审核队列'
        with database() as db:
            db.execute('INSERT INTO post(kind, body, state, reason, day, mine) VALUES (?, ?, ?, ?, ?, 1)',
                       (kind, body, state, reason, date.today().isoformat()))
        return jsonify(state=state, reason=reason)

    @pages.post('/posts/<int:item_id>/withdraw')
    def withdraw(item_id):
        with database() as db:
            if not db.execute("""UPDATE post SET state = 'withdrawn', reason = '作者撤回'
                                 WHERE id = ? AND mine = 1 AND state IN ('pending', 'published')""",
                              (item_id,)).rowcount:
                abort(409, '稿件状态已变化，请刷新')
        return jsonify(ok=True)

    @pages.post('/review/login')
    def login():
        data = payload()
        supplied = data.get('password')
        if (data.get('username') != 'reviewer' or not isinstance(supplied, str)
                or not compare_digest(supplied.encode(), reviewer_password.encode())):
            abort(401, '账号或口令不正确')
        return jsonify(token=reviewer_token)

    def require_reviewer():
        authorization = request.headers.get('Authorization', '').encode()
        if not compare_digest(authorization, f'Bearer {reviewer_token}'.encode()):
            abort(401, '请先登录审核台')

    @pages.get('/review/posts')
    def review_posts():
        require_reviewer()
        with database() as db:
            return jsonify([dict(row) for row in db.execute(
                'SELECT id, kind, body, state, reason, day FROM post ORDER BY id DESC')])

    @pages.post('/review/posts/<int:item_id>')
    def review(item_id):
        require_reviewer()
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
        with database() as db:
            if not db.execute('UPDATE post SET state = ?, reason = ? WHERE id = ? AND state = ?',
                              (state, reason.strip() or default_reason, item_id, previous)).rowcount:
                abort(409, '稿件状态已变化，请刷新')
        return jsonify(ok=True)

    return pages
