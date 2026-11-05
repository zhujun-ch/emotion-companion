"""Verify the running chat API, Ollama reply, and SQLite persistence."""
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

from dotenv import load_dotenv
import requests

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
base = 'http://127.0.0.1:' + os.getenv('APP_PORT', '5000')
user_id = 'smoke_' + uuid.uuid4().hex[:12]
text = '我今天拿到了奖学金，心情特别好，想和你分享。'
health = requests.get(base + '/api/ping', timeout=10)
health.raise_for_status()
started = time.perf_counter()
response = requests.post(base + '/api/chat', json={'user_id': user_id, 'text': text}, timeout=200)
response.raise_for_status()
result = response.json()
assert result['status'] == 'success', result
assert result['reply'].strip(), 'Empty model reply'
assert 0 <= result['confidence'] <= 1
if os.getenv('DB_BACKEND', 'mysql') == 'sqlite':
    with sqlite3.connect(ROOT / os.getenv('SQLITE_PATH', 'artifacts/demo.sqlite3')) as db:
        row = db.execute('SELECT user_text, emotion_label, llm_reply FROM emotion_record WHERE user_id=?', (user_id,)).fetchone()
    assert row == (text, result['emotion_label'], result['reply']), 'Saved record mismatch'
result['seconds'] = round(time.perf_counter() - started, 2)
result['database_verified'] = os.getenv('DB_BACKEND') == 'sqlite'
out = ROOT / 'artifacts' / 'last-smoke-test.json'
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
print('PASS: API -> TextCNN -> Ollama -> database')
