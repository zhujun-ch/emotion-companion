"""Durable request receipts, committed in the same transaction as their writes."""
import json
import re
from hashlib import sha256
from uuid import uuid4

from flask import abort, request


def initialize_receipts(db):
    db.execute('''CREATE TABLE IF NOT EXISTS request_receipt (
        user_id TEXT NOT NULL, scope TEXT NOT NULL, request_id TEXT NOT NULL,
        fingerprint TEXT NOT NULL, response TEXT NOT NULL,
        PRIMARY KEY(user_id, scope, request_id)
    )''')


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
    row = db.execute('''SELECT fingerprint, response FROM request_receipt
        WHERE user_id=? AND scope=? AND request_id=?''', (owner, scope, request_id)).fetchone()
    if row is None:
        return None
    if row['fingerprint'] != content_hash:
        abort(409, '该请求编号已用于其他内容，请勿重复使用')
    return json.loads(row['response'])


def remember(db, owner, scope, request_id, content_hash, response):
    response = response | {'request_id': request_id}
    db.execute('INSERT INTO request_receipt VALUES (?, ?, ?, ?, ?)',
               (owner, scope, request_id, content_hash, json.dumps(response, ensure_ascii=False)))
    return response
