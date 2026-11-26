"""Durable request receipts, committed in the same transaction as their writes."""
import json
import os
import re
from hashlib import sha256
from time import time
from uuid import uuid4

from flask import abort, request


def receipt_ttl():
    ttl = int(os.getenv('REQUEST_RECEIPT_TTL_SECONDS', str(7 * 86400)))
    if ttl < 60:
        raise RuntimeError('REQUEST_RECEIPT_TTL_SECONDS 须不小于 60 秒')
    return ttl


def prune_receipts(db, now=None):
    cutoff = (int(time()) if now is None else int(now)) - receipt_ttl()
    db.execute('DELETE FROM request_receipt WHERE created_at IS NOT NULL AND created_at <= ?', (cutoff,))


def initialize_receipts(db):
    db.execute('''CREATE TABLE IF NOT EXISTS request_receipt (
        user_id TEXT NOT NULL, scope TEXT NOT NULL, request_id TEXT NOT NULL,
        fingerprint TEXT NOT NULL, response TEXT NOT NULL,
        created_at INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(user_id, scope, request_id)
    )''')
    columns = {row['name'] for row in db.execute('PRAGMA table_info(request_receipt)')}
    if 'created_at' not in columns:
        db.execute('ALTER TABLE request_receipt ADD COLUMN created_at INTEGER')
    db.execute('UPDATE request_receipt SET created_at=? WHERE created_at IS NULL OR created_at=0', (int(time()),))
    db.execute('CREATE INDEX IF NOT EXISTS idx_request_receipt_created ON request_receipt(created_at)')
    prune_receipts(db)


def request_identity(payload):
    header = request.headers.get('X-Request-ID')
    supplied = payload.get('request_id')
    if header is not None and supplied is not None and header != supplied:
        abort(400, '请求编号不一致')
    value = header if header is not None else supplied
    # Legacy callers receive an ID, but must reuse it themselves to retry safely.
    if value is None:
        return uuid4().hex
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,128}', value):
        abort(400, '请求编号须为 8 至 128 位字母、数字、下划线或连字符')
    return value


def fingerprint(payload):
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':')).encode()).hexdigest()


def receipt(db, owner, scope, request_id, content_hash):
    row = db.execute('''SELECT fingerprint, response, created_at FROM request_receipt
        WHERE user_id=? AND scope=? AND request_id=?''', (owner, scope, request_id)).fetchone()
    if row is None:
        return None
    if row['created_at'] is not None and row['created_at'] <= int(time()) - receipt_ttl():
        return None
    if row['fingerprint'] != content_hash:
        abort(409, '该请求编号已用于其他内容，请勿重复使用')
    return json.loads(row['response'])


def remember(db, owner, scope, request_id, content_hash, response):
    now = int(time())
    prune_receipts(db, now)
    response = response | {'request_id': request_id}
    db.execute('''INSERT OR REPLACE INTO request_receipt(user_id, scope, request_id, fingerprint, response, created_at)
        VALUES (?, ?, ?, ?, ?, ?)''',
               (owner, scope, request_id, content_hash, json.dumps(response, ensure_ascii=False), now))
    return response
