"""Shared fixture data and interactions for the local three-front-end demo."""
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from hmac import digest
from secrets import token_urlsafe
from time import time
import sqlite3

from flask import Blueprint, abort, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
from request_dedup import initialize_receipts, request_identity, fingerprint, receipt, remember
from deployment_access import initialize_attempts, consume_attempt

MOODS = ('平静', '开心', '低落', '紧张', '生气', '惊喜')
KINDS = ('鼓励', '倾诉')


def create_demo_pages(path, reviewer_password, moderate_post, *, diary_owner, reviewer_username='admin', reviewer_password_hash=None):
    pages = Blueprint('demo_pages', __name__, url_prefix='/api/demo')
    password_hash = reviewer_password_hash or generate_password_hash(reviewer_password)
    # Use the configured credential to invalidate reviewer sessions on rotation.
    session_key = reviewer_password_hash or reviewer_password

    @contextmanager
    def database():
        db = sqlite3.connect(path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    with database() as db:
        db.execute('PRAGMA journal_mode=WAL')
        initialize_receipts(db)
        initialize_attempts(db)
        db.executescript("""
            CREATE TABLE IF NOT EXISTS diary (
                id INTEGER PRIMARY KEY, day TEXT NOT NULL,
                mood TEXT NOT NULL, body TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS post (
                id INTEGER PRIMARY KEY, kind TEXT NOT NULL, body TEXT NOT NULL,
                state TEXT NOT NULL, reason TEXT NOT NULL,
                day TEXT NOT NULL
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
            CREATE TABLE IF NOT EXISTS post_comment (
                id INTEGER PRIMARY KEY, post_id INTEGER NOT NULL,
                body TEXT NOT NULL, state TEXT NOT NULL, reason TEXT NOT NULL,
                day TEXT NOT NULL, author TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_post_comment_post ON post_comment(post_id, state, id);
            CREATE TABLE IF NOT EXISTS comment_audit (
                id INTEGER PRIMARY KEY, comment_id INTEGER NOT NULL, post_id INTEGER NOT NULL,
                actor TEXT NOT NULL, action TEXT NOT NULL, state TEXT NOT NULL,
                reason TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        diary_columns = {row['name'] for row in db.execute('PRAGMA table_info(diary)')}
        if 'user_id' not in diary_columns:
            db.execute('ALTER TABLE diary ADD COLUMN user_id TEXT')
        db.execute('CREATE INDEX IF NOT EXISTS idx_diary_user_day ON diary(user_id, day)')
        columns = {row['name'] for row in db.execute('PRAGMA table_info(post)')}
        if 'author' not in columns:
            db.execute('ALTER TABLE post ADD COLUMN author TEXT')
        if 'mine' in columns:
            db.execute('ALTER TABLE post DROP COLUMN mine')
        for table in ('post', 'post_comment', 'post_author'):
            if 'user_id' not in {r['name'] for r in db.execute(f'PRAGMA table_info({table})')}:
                db.execute(f'ALTER TABLE {table} ADD COLUMN user_id TEXT')
        for table in ('post', 'post_comment'):
            if 'created_at' not in {r['name'] for r in db.execute(f'PRAGMA table_info({table})')}:
                db.execute(f'ALTER TABLE {table} ADD COLUMN created_at TEXT')
        db.execute('CREATE INDEX IF NOT EXISTS idx_post_user ON post(user_id, id)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_comment_user ON post_comment(user_id, id)')
        comment_columns = {row['name'] for row in db.execute('PRAGMA table_info(post_comment)')}
        if 'parent_comment_id' not in comment_columns:
            db.execute('ALTER TABLE post_comment ADD COLUMN parent_comment_id INTEGER REFERENCES post_comment(id)')
        if db.execute('INSERT OR IGNORE INTO demo_seed VALUES (1)').rowcount:
            today = date.today()
            db.executemany(
                'INSERT INTO post(kind, body, state, reason, day) VALUES (?, ?, ?, ?, ?)',
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
    @pages.errorhandler(429)
    @pages.errorhandler(410)
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

    def int_arg(name, default=None, *, minimum=0, maximum=None):
        raw = request.args.get(name)
        if raw is None or raw == '':
            return default
        try:
            value = int(raw)
        except ValueError:
            abort(400, f'参数 {name} 须为整数')
        if value < minimum or (maximum is not None and value > maximum):
            abort(400, f'参数 {name} 超出允许范围')
        return value

    def paginated_array(items, has_more, *, next_offset=None, next_before_id=None):
        response = jsonify(items)
        response.headers['X-Has-More'] = '1' if has_more else '0'
        if has_more and next_offset is not None:
            response.headers['X-Next-Offset'] = str(next_offset)
        if has_more and next_before_id is not None:
            response.headers['X-Next-Before-Id'] = str(next_before_id)
        return response

    @pages.get('/diaries')
    def list_diaries():
        owner = diary_owner()
        limit = int_arg('limit', 100, minimum=1, maximum=500)
        offset = int_arg('offset', 0, minimum=0)
        clauses = ['user_id = ?']
        params = [owner]
        for param_name, op in (('from_day', '>='), ('to_day', '<=')):
            raw_day = request.args.get(param_name)
            if raw_day:
                try:
                    parsed = date.fromisoformat(raw_day).isoformat()
                except ValueError:
                    abort(400, '日期格式无效')
                clauses.append(f'day {op} ?')
                params.append(parsed)
        params.extend([limit + 1, offset])
        with database() as db:
            rows = db.execute(
                f'SELECT id, day, mood, body FROM diary WHERE {" AND ".join(clauses)} ORDER BY day DESC, id DESC LIMIT ? OFFSET ?',
                params,
            ).fetchall()
        has_more = len(rows) > limit
        items = [dict(row) for row in rows[:limit]]
        return paginated_array(items, has_more, next_offset=offset + len(items))

    @pages.route('/diaries', methods=['POST'])
    @pages.route('/diaries/<int:item_id>', methods=['PUT', 'DELETE'])
    def change_diary(item_id=None):
        owner = diary_owner()
        if request.method == 'DELETE':
            with database() as db:
                if not db.execute('DELETE FROM diary WHERE id = ? AND user_id = ?', (item_id, owner)).rowcount:
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
        request_id = request_identity(data) if item_id is None else None
        content_hash = fingerprint({'day': day, 'mood': mood, 'body': body})
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            if item_id is None:
                previous = receipt(db, owner, 'diary', request_id, content_hash)
                if previous is not None:
                    return jsonify(previous)
                db.execute('INSERT INTO diary(day, mood, body, user_id) VALUES (?, ?, ?, ?)', (day, mood, body, owner))
                return jsonify(remember(db, owner, 'diary', request_id, content_hash, {'ok': True}))
            elif not db.execute('UPDATE diary SET day = ?, mood = ?, body = ? WHERE id = ? AND user_id = ?',
                                (day, mood, body, item_id, owner)).rowcount:
                abort(404, '日记已不存在')
        return jsonify(ok=True)

    def hash_token(token):
        return sha256(token.encode()).hexdigest()

    def hash_reviewer_token(token):
        identity = f'{reviewer_username}:{token}'.encode()
        return digest(session_key.encode(), identity, 'sha256').hex()

    def audit(db, post_id, actor, action, state, reason):
        db.execute('INSERT INTO post_audit(post_id, actor, action, state, reason) VALUES (?, ?, ?, ?, ?)',
                   (post_id, actor, action, state, reason))

    def audit_comment(db, comment_id, post_id, actor, action, state, reason):
        db.execute('''INSERT INTO comment_audit(comment_id, post_id, actor, action, state, reason)
                      VALUES (?, ?, ?, ?, ?, ?)''', (comment_id, post_id, actor, action, state, reason))

    @pages.post('/posts/session')
    def start_post_session():
        abort(410, '投稿已升级为账号归属，请登录并更新客户端')

    @pages.post('/posts/claim')
    def claim_posts():
        owner = diary_owner()
        token = request.headers.get('X-Treehole-Token', '')
        if not token or len(token) > 128:
            abort(400, '缺少旧投稿凭据')
        author = hash_token(token)
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT user_id FROM post_author WHERE token_hash=?', (author,)).fetchone()
            if row is None:
                abort(401, '旧投稿凭据无效')
            if row['user_id'] is not None and row['user_id'] != owner:
                abort(409, '该设备的旧投稿已关联其他账号')
            db.execute('UPDATE post_author SET user_id=? WHERE token_hash=?', (owner, author))
            posts = db.execute('UPDATE post SET user_id=? WHERE author=? AND user_id IS NULL', (owner, author)).rowcount
            comments = db.execute('UPDATE post_comment SET user_id=? WHERE author=? AND user_id IS NULL', (owner, author)).rowcount
        return jsonify(ok=True, posts=posts, comments=comments)

    @pages.get('/posts')
    def list_posts():
        owner = diary_owner() if request.headers.get('Authorization') else None
        limit = int_arg('limit', 30, minimum=1, maximum=100)
        before_id = int_arg('before_id', None, minimum=1)
        mine_limit = int_arg('mine_limit', 50, minimum=1, maximum=100)
        mine_before_id = int_arg('mine_before_id', None, minimum=1)
        mine_comments_before_id = int_arg('mine_comments_before_id', None, minimum=1)
        with database() as db:
            pub_where = "state = 'published'"
            pub_params = []
            if before_id is not None:
                pub_where += ' AND id < ?'
                pub_params.append(before_id)
            pub_params.append(limit + 1)
            pub_rows = db.execute(
                f'SELECT id, kind, body, day FROM post WHERE {pub_where} ORDER BY id DESC LIMIT ?',
                pub_params,
            ).fetchall()
            public_has_more = len(pub_rows) > limit
            public = [dict(row) for row in pub_rows[:limit]]
            grouped = {item['id']: [] for item in public}
            if public:
                placeholders = ','.join('?' for _ in public)
                post_ids = [item['id'] for item in public]
                comments = db.execute(f'''SELECT c.id, c.post_id, c.body, c.day, c.parent_comment_id,
                                                parent.body AS parent_body FROM post_comment c
                                         JOIN post p ON p.id = c.post_id
                                         LEFT JOIN post_comment parent ON parent.id = c.parent_comment_id
                                             AND parent.post_id = c.post_id AND parent.state = 'published'
                                         WHERE c.state = 'published' AND p.state = 'published'
                                           AND c.post_id IN ({placeholders})
                                         ORDER BY c.id''', post_ids)
                for row in comments:
                    grouped[row['post_id']].append(dict(row))
            for item in public:
                item['comments'] = grouped[item['id']]
            public_next_before_id = public[-1]['id'] if public_has_more and public else None

            if owner is not None:
                mine_where = 'user_id = ?'
                mine_params = [owner]
                if mine_before_id is not None:
                    mine_where += ' AND id < ?'
                    mine_params.append(mine_before_id)
                mine_params.append(mine_limit + 1)
                mine_rows = db.execute(
                    f'SELECT id, kind, body, state, reason, day, created_at FROM post WHERE {mine_where} ORDER BY id DESC LIMIT ?',
                    mine_params,
                ).fetchall()
                mine_has_more = len(mine_rows) > mine_limit
                mine = [dict(row) for row in mine_rows[:mine_limit]]
                mine_next_before_id = mine[-1]['id'] if mine_has_more and mine else None

                mc_where = 'c.user_id = ?'
                mc_params = [owner]
                if mine_comments_before_id is not None:
                    mc_where += ' AND c.id < ?'
                    mc_params.append(mine_comments_before_id)
                mc_params.append(mine_limit + 1)
                mc_rows = db.execute(f'''SELECT c.id, c.post_id, c.body, c.state, c.reason, c.day, c.created_at, c.parent_comment_id,
                                                p.body AS post_body FROM post_comment c
                                         JOIN post p ON p.id = c.post_id
                                         WHERE {mc_where} ORDER BY c.id DESC LIMIT ?''', mc_params).fetchall()
                mine_comments_has_more = len(mc_rows) > mine_limit
                mine_comments = [dict(row) for row in mc_rows[:mine_limit]]
                mine_comments_next_before_id = mine_comments[-1]['id'] if mine_comments_has_more and mine_comments else None
            else:
                mine, mine_has_more, mine_next_before_id = [], False, None
                mine_comments, mine_comments_has_more, mine_comments_next_before_id = [], False, None

            return jsonify(
                public=public,
                public_has_more=public_has_more,
                public_next_before_id=public_next_before_id,
                mine=mine,
                mine_has_more=mine_has_more,
                mine_next_before_id=mine_next_before_id,
                mine_comments=mine_comments,
                mine_comments_has_more=mine_comments_has_more,
                mine_comments_next_before_id=mine_comments_next_before_id,
            )

    @pages.post('/posts')
    def submit_post():
        owner = diary_owner()
        data = payload()
        kind = data.get('kind')
        if kind not in KINDS:
            abort(400, '请选择投稿类型')
        body = body_text(data, 500)
        request_id = request_identity(data)
        content_hash = fingerprint({'kind': kind, 'body': body})
        with database() as db:
            previous = receipt(db, owner, 'post', request_id, content_hash)
            if previous is not None:
                return jsonify(previous)
        state, reason = moderate_post(body)
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = receipt(db, owner, 'post', request_id, content_hash)
            if previous is not None:
                return jsonify(previous)
            created_at = datetime.now(timezone.utc).isoformat(timespec='microseconds')
            item_id = db.execute(
                'INSERT INTO post(kind, body, state, reason, day, user_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (kind, body, state, reason, date.today().isoformat(), owner, created_at),
            ).lastrowid
            audit(db, item_id, '系统', 'auto', state, reason)
            result = remember(db, owner, 'post', request_id, content_hash, dict(id=item_id, state=state, reason=reason))
        return jsonify(result)

    @pages.post('/posts/<int:item_id>/comments')
    def submit_comment(item_id):
        owner = diary_owner()
        data = payload()
        body = body_text(data, 300)
        parent_id = data.get('parent_comment_id')
        if parent_id is not None and (type(parent_id) is not int or not 0 < parent_id < 2**63):
            abort(400, '回复对象无效')
        published_target = """SELECT id FROM post WHERE id = ? AND state = 'published'
            AND (? IS NULL OR EXISTS (SELECT 1 FROM post_comment
                WHERE id = ? AND post_id = post.id AND state = 'published'))"""
        target = (item_id, parent_id, parent_id)
        request_id = request_identity(data)
        content_hash = fingerprint({'post_id': item_id, 'body': body, 'parent_comment_id': parent_id})
        with database() as db:
            previous = receipt(db, owner, 'comment', request_id, content_hash)
            if previous is not None:
                return jsonify(previous)
            if not db.execute(published_target, target).fetchone():
                abort(404, '这条留言或回复已不可回复')
        state, reason = moderate_post(body)
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = receipt(db, owner, 'comment', request_id, content_hash)
            if previous is not None:
                return jsonify(previous)
            created_at = datetime.now(timezone.utc).isoformat(timespec='microseconds')
            inserted = db.execute(f'''INSERT INTO post_comment(post_id, body, state, reason, day, author, parent_comment_id, user_id, created_at)
                SELECT id, ?, ?, ?, ?, '', ?, ?, ? FROM ({published_target})''',
                (body, state, reason, date.today().isoformat(), parent_id, owner, created_at, *target))
            if not inserted.rowcount:
                abort(409, '回复对象状态已变化，请刷新')
            comment_id = inserted.lastrowid
            audit_comment(db, comment_id, item_id, '系统', 'auto', state, reason)
            result = remember(db, owner, 'comment', request_id, content_hash, dict(id=comment_id, state=state, reason=reason))
        return jsonify(result)

    @pages.post('/comments/<int:comment_id>/withdraw')
    def withdraw_comment(comment_id):
        owner = diary_owner()
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT post_id FROM post_comment WHERE id = ? AND user_id = ?',
                             (comment_id, owner)).fetchone()
            if row is None:
                abort(404, '回复不存在')
            if not db.execute('''UPDATE post_comment SET state = 'withdrawn', reason = '作者撤回'
                                 WHERE id = ? AND user_id = ? AND state IN ('pending', 'published')''',
                              (comment_id, owner)).rowcount:
                abort(409, '回复状态已变化，请刷新')
            audit_comment(db, comment_id, row['post_id'], '作者', 'withdraw', 'withdrawn', '作者撤回')
        return jsonify(ok=True)

    @pages.post('/posts/<int:item_id>/withdraw')
    def withdraw(item_id):
        owner = diary_owner()
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM post WHERE id = ? AND user_id = ?',
                              (item_id, owner)).fetchone():
                abort(404, '投稿不存在')
            if not db.execute('''UPDATE post SET state = 'withdrawn', reason = '作者撤回'
                                 WHERE id = ? AND user_id = ? AND state IN ('pending', 'published')''',
                              (item_id, owner)).rowcount:
                abort(409, '稿件状态已变化，请刷新')
            audit(db, item_id, '作者', 'withdraw', 'withdrawn', '作者撤回')
        return jsonify(ok=True)

    @pages.post('/review/login')
    def login():
        data = payload()
        supplied = data.get('password')
        consume_attempt(database, 'reviewer', str(data.get('username') or '').strip())
        if (data.get('username') != reviewer_username or not isinstance(supplied, str)
                or len(supplied) > 128 or not check_password_hash(password_hash, supplied)):
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
            if request.headers.get('X-Treehole-Token'):
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
        limit = int_arg('limit', 100, minimum=1, maximum=200)
        offset = int_arg('offset', 0, minimum=0)
        with database() as db:
            require_reviewer(db)
            rows = db.execute('''
                SELECT id, post_id, NULL AS comment_id, 'post' AS target_type,
                       actor, action, state, reason, created_at FROM post_audit
                UNION ALL
                SELECT id, post_id, comment_id, 'comment' AS target_type,
                       actor, action, state, reason, created_at FROM comment_audit
                ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?''', (limit + 1, offset)).fetchall()
        has_more = len(rows) > limit
        items = [dict(row) for row in rows[:limit]]
        return paginated_array(items, has_more, next_offset=offset + len(items))

    REVIEW_STATES = ('pending', 'published', 'blocked', 'rejected', 'removed', 'withdrawn')

    @pages.get('/review/posts')
    def review_posts():
        limit = int_arg('limit', 100, minimum=1, maximum=200)
        before_id = int_arg('before_id', None, minimum=1)
        state = request.args.get('state')
        if state and state not in REVIEW_STATES:
            abort(400, '无效的审核状态')
        clauses = []
        params = []
        if state:
            clauses.append('state = ?')
            params.append(state)
        if before_id is not None:
            clauses.append('id < ?')
            params.append(before_id)
        where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
        params.append(limit + 1)
        with database() as db:
            require_reviewer(db)
            rows = db.execute(
                f'SELECT id, kind, body, state, reason, day FROM post {where} ORDER BY id DESC LIMIT ?',
                params,
            ).fetchall()
        has_more = len(rows) > limit
        items = [dict(row) for row in rows[:limit]]
        return paginated_array(items, has_more, next_before_id=items[-1]['id'] if items else None)

    @pages.get('/review/comments')
    def review_comments():
        limit = int_arg('limit', 100, minimum=1, maximum=200)
        before_id = int_arg('before_id', None, minimum=1)
        state = request.args.get('state')
        if state and state not in REVIEW_STATES:
            abort(400, '无效的审核状态')
        clauses = []
        params = []
        if state:
            clauses.append('c.state = ?')
            params.append(state)
        if before_id is not None:
            clauses.append('c.id < ?')
            params.append(before_id)
        where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
        params.append(limit + 1)
        with database() as db:
            require_reviewer(db)
            rows = db.execute(f'''
                SELECT c.id, c.post_id, c.body, c.state, c.reason, c.day, c.parent_comment_id,
                       p.body AS post_body FROM post_comment c
                JOIN post p ON p.id = c.post_id {where} ORDER BY c.id DESC LIMIT ?''', params).fetchall()
        has_more = len(rows) > limit
        items = [dict(row) for row in rows[:limit]]
        return paginated_array(items, has_more, next_before_id=items[-1]['id'] if items else None)

    def parse_review_request():
        data = payload()
        action = str(data.get('action'))
        transition = {
            'approve': ('pending', 'published', '人工审核通过'),
            'reject': ('pending', 'rejected', '人工审核驳回'),
            'remove': ('published', 'removed', '管理员下架'),
        }.get(action)
        if transition is None:
            abort(400, '未知审核操作')
        previous, state, default_reason = transition
        reason = data.get('reason', '')
        if not isinstance(reason, str) or len(reason.strip()) > 120:
            abort(400, '审核原因最多 120 字')
        if state == 'rejected' and not reason.strip():
            abort(400, '请填写驳回原因')
        return action, previous, state, reason.strip() or default_reason

    @pages.post('/review/comments/<int:comment_id>')
    def review_comment(comment_id):
        action, previous, state, reason = parse_review_request()
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            require_reviewer(db)
            row = db.execute('SELECT post_id FROM post_comment WHERE id = ?', (comment_id,)).fetchone()
            if row is None:
                abort(404, '回复不存在')
            if state == 'published' and not db.execute(
                    "SELECT 1 FROM post WHERE id = ? AND state = 'published'", (row['post_id'],)).fetchone():
                abort(409, '原留言已下架，无法发布回复')
            if not db.execute('UPDATE post_comment SET state = ?, reason = ? WHERE id = ? AND state = ?',
                              (state, reason, comment_id, previous)).rowcount:
                abort(409, '回复状态已变化，请刷新')
            audit_comment(db, comment_id, row['post_id'], reviewer_username, action, state, reason)
        return jsonify(ok=True)

    @pages.post('/review/posts/<int:item_id>')
    def review(item_id):
        action, previous, state, reason = parse_review_request()
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            require_reviewer(db)
            if db.execute('SELECT 1 FROM post WHERE id = ?', (item_id,)).fetchone() is None:
                abort(404, '稿件不存在')
            if not db.execute('UPDATE post SET state = ?, reason = ? WHERE id = ? AND state = ?',
                              (state, reason, item_id, previous)).rowcount:
                abort(409, '稿件状态已变化，请刷新')
            audit(db, item_id, reviewer_username, action, state, reason)
        return jsonify(ok=True)

    return pages
