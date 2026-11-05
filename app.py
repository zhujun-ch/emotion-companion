from flask import Flask, request, jsonify
from flask_cors import CORS
import pymysql
import requests
import torch
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from conversation_store import ConversationStore
from threading import Lock
from emotion_model import EmotionPredictor

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
CORS(app)


# Train/inference share the same vocabulary, tokenizer, model config, and label mapping.
EMOTION_MODEL_DIR = BASE_DIR / os.getenv("EMOTION_MODEL_DIR", "artifacts/emotion_cnn")
torch.set_num_threads(int(os.getenv("EMOTION_CPU_THREADS", "4")))
print("正在加载训练后的六分类 TextCNN...")
emotion_predictor = EmotionPredictor(EMOTION_MODEL_DIR)
print("情绪模型加载完成：", ", ".join(emotion_predictor.config['label_names']))


def predict_emotion(text):
    return emotion_predictor.predict(text)


DB_BACKEND = os.getenv("DB_BACKEND", "mysql").lower()
SQLITE_PATH = BASE_DIR / os.getenv("SQLITE_PATH", "artifacts/demo.sqlite3")


def get_db_conn():
    if DB_BACKEND == "sqlite":
        return sqlite3.connect(SQLITE_PATH)
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "psych_db"), charset="utf8mb4",
        connect_timeout=5,
    )


if DB_BACKEND == "sqlite":
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS emotion_record (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            user_text TEXT NOT NULL,
            emotion_label TEXT NOT NULL,
            confidence REAL NOT NULL,
            llm_reply TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")


conversation_store = ConversationStore(
    SQLITE_PATH if DB_BACKEND == 'sqlite' else BASE_DIR / 'artifacts/conversations.sqlite3',
    save_emotion_records=DB_BACKEND == 'sqlite',
)
conversation_locks = {}


def ask_ollama(user_text, emotion_label, history=None):
    system_prompt = (
        "你是一个温暖、有共情力的心理陪伴者。"
        "用户正在向你倾诉，请用温和、支持性的语气回复，"
        "不要给出医学诊断，不要评判用户。"
        f"当前识别到的情绪倾向是：{emotion_label}。"
    )
    response = requests.post(
        os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/") + "/v1/chat/completions",
        json={
            "model": os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
            "messages": [{"role": "system", "content": system_prompt}]
                        + (history or []) + [{"role": "user", "content": user_text}],
            "stream": False,
            "temperature": 0.5,
            "max_tokens": 256,
        },
        timeout=float(os.getenv("OLLAMA_TIMEOUT", "180")),
    )
    response.raise_for_status()
    reply = response.json()["choices"][0]["message"]["content"]
    if not isinstance(reply, str) or not reply.strip():
        raise ValueError("Ollama returned an empty reply")
    return reply


@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({"status": "success", "msg": "后端服务已启动！",
                    "emotion_model": {"name": "TextCNN", "labels": emotion_predictor.config["label_names"]}})


def valid_user_id(value):
    return isinstance(value, str) and 0 < len(value.strip()) <= 128


@app.errorhandler(sqlite3.Error)
def storage_error(error):
    app.logger.exception("会话存储失败")
    return jsonify({"status": "error", "msg": "会话保存失败，请稍后重试"}), 503


@app.route('/api/sessions', methods=['GET', 'POST'])
def sessions():
    data = request.get_json(silent=True) if request.method == 'POST' else request.args
    if not isinstance(data, (dict, type(request.args))):
        return jsonify({"status": "error", "msg": "请提交有效参数"}), 400
    user_id = data.get('user_id', 'test_user')
    if not valid_user_id(user_id):
        return jsonify({"status": "error", "msg": "用户标识无效"}), 400
    if request.method == 'POST':
        return jsonify({"status": "success", "session": conversation_store.create(user_id)}), 201
    return jsonify({"status": "success", "sessions": conversation_store.list(user_id)})


@app.route('/api/sessions/<session_id>/messages', methods=['GET'])
def session_messages(session_id):
    user_id = request.args.get('user_id', 'test_user')
    session = conversation_store.get(session_id, user_id)
    if not session:
        return jsonify({"status": "error", "msg": "对话不存在"}), 404
    return jsonify({"status": "success", "session": session,
                    "messages": conversation_store.messages(session_id)})


@app.route('/api/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    lock = conversation_locks.setdefault(session_id, Lock())
    if not lock.acquire(blocking=False):
        return jsonify({"status": "error", "msg": "正在回复，请稍后再删除"}), 409
    try:
        if not conversation_store.delete(session_id, request.args.get('user_id', 'test_user')):
            return jsonify({"status": "error", "msg": "对话不存在"}), 404
        return jsonify({"status": "success"})
    finally:
        lock.release()


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"status": "error", "msg": "请提交 JSON 对象"}), 400
    user_text = data.get('text', '')
    user_id = data.get('user_id', 'test_user')
    if not isinstance(user_text, str) or not user_text.strip():
        return jsonify({"status": "error", "msg": "文本不能为空"}), 400
    user_text = user_text.strip()
    if len(user_text) > 2000 or not valid_user_id(user_id):
        return jsonify({"status": "error", "msg": "文本最多 2000 字，且需提供有效用户标识"}), 400
    session_id = data.get('session_id')
    if session_id is not None:
        if not isinstance(session_id, str) or not conversation_store.get(session_id, user_id):
            return jsonify({"status": "error", "msg": "对话不存在，请新建对话"}), 404
    else:
        # Compatibility: old clients may omit session_id and still get a single-turn reply.
        session_id = conversation_store.create(user_id)['id']
    lock = conversation_locks.setdefault(session_id, Lock())
    if not lock.acquire(blocking=False):
        return jsonify({"status": "error", "msg": "这段对话正在回复，请稍后再发"}), 409
    try:
        history = conversation_store.context(session_id, max_turns=8, char_budget=max(0, 2400 - len(user_text)))
        emotion_label, confidence = predict_emotion(user_text)
        try:
            reply = ask_ollama(user_text, emotion_label, history)
        except (requests.RequestException, ValueError, KeyError, IndexError):
            app.logger.exception("Ollama 调用失败")
            return jsonify({"status": "error", "msg": "模型调用失败，请检查 Ollama 服务和模型是否就绪"}), 502
        try:
            if DB_BACKEND != 'sqlite':
                conn = get_db_conn()
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("INSERT INTO emotion_record (user_id,user_text,emotion_label,confidence,llm_reply) VALUES (%s,%s,%s,%s,%s)",
                                       (user_id, user_text, emotion_label, confidence, reply))
                    conn.commit()
                finally:
                    conn.close()
            user_message_id, assistant_message_id = conversation_store.save_turn(
                session_id, user_id, user_text, reply, emotion_label, confidence)
        except (sqlite3.Error, pymysql.MySQLError, LookupError):
            app.logger.exception("聊天记录写入失败")
            return jsonify({"status": "error", "msg": "聊天记录保存失败，请检查数据库"}), 503
        return jsonify({"status": "success", "session_id": session_id,
                        "user_message_id": user_message_id, "assistant_message_id": assistant_message_id,
                        "context_turns": len(history) // 2, "emotion_label": emotion_label,
                        "confidence": confidence, "reply": reply})
    finally:
        lock.release()


if __name__ == '__main__':
    app.run(host=os.getenv("APP_HOST", "127.0.0.1"),
            port=int(os.getenv("APP_PORT", "5000")), debug=False)
