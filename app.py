from flask import Flask, request, jsonify
from flask_cors import CORS
import pymysql
import requests
import torch
import torch.nn as nn
import jieba
import pickle
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from conversation_store import ConversationStore
from threading import Lock

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
CORS(app)


# ==========================================
# 1. 定义 TextCNN 模型结构 (必须和训练时一模一样)
# ==========================================
class TextCNN(nn.Module):
    def __init__(self, vocab_size, embed_dim, num_classes):
        super(TextCNN, self).__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        self.conv1 = nn.Conv2d(1, 100, (2, embed_dim))
        self.conv2 = nn.Conv2d(1, 100, (3, embed_dim))
        self.conv3 = nn.Conv2d(1, 100, (4, embed_dim))
        self.dropout = nn.Dropout(0.5)
        self.fc = nn.Linear(300, num_classes)

    def forward(self, x):
        x = self.embedding(x)
        x = x.unsqueeze(1)
        x1 = torch.relu(self.conv1(x)).squeeze(3)
        x1 = torch.max_pool1d(x1, x1.size(2)).squeeze(2)
        x2 = torch.relu(self.conv2(x)).squeeze(3)
        x2 = torch.max_pool1d(x2, x2.size(2)).squeeze(2)
        x3 = torch.relu(self.conv3(x)).squeeze(3)
        x3 = torch.max_pool1d(x3, x3.size(2)).squeeze(2)
        x = torch.cat((x1, x2, x3), 1)
        x = self.dropout(x)
        return self.fc(x)


# ==========================================
# 2. 启动时加载模型和词表 (全局加载，避免每次请求都加载导致卡顿)
# ==========================================
print("正在加载情绪识别模型...")
with (BASE_DIR / "word2id.pkl").open("rb") as f:
    word2id = pickle.load(f)
device = torch.device("cpu")
emotion_model = TextCNN(len(word2id), embed_dim=100, num_classes=5).to(device)
emotion_model.load_state_dict(torch.load(BASE_DIR / "textcnn_model.pth", map_location=device, weights_only=True))
emotion_model.eval()
id2label = {0: "快乐", 1: "焦虑", 2: "悲伤", 3: "愤怒", 4: "压力大"}
MAX_LEN = 20


def predict_emotion(text):
    seq = [word2id.get(word, 1) for word in jieba.cut(text)][:MAX_LEN]
    seq += [0] * (MAX_LEN - len(seq))
    tensor_x = torch.tensor([seq], dtype=torch.long, device=device)
    with torch.no_grad():
        probabilities = torch.softmax(emotion_model(tensor_x), dim=1)
        confidence, predicted = torch.max(probabilities, 1)
    return id2label[predicted.item()], confidence.item()


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
        "你是一位温暖、耐心的倾听者，像朋友一样和用户聊天。\n"
        "- 先回应用户刚才说的具体内容，不要复述情绪标签。\n"
        "- 用口语、短句，一次回 2-4 句话，不要列清单、不要说教。\n"
        "- 用户只想倾诉时就陪着聊，不主动给建议；只有用户问‘怎么办’时再给一个温和的建议。\n"
        "- 倾诉时不要追问‘从中学到了什么’、要求总结收获或催促振作；避免空泛地说‘相信自己’、‘一切都会好’。\n"
        "- 不做心理诊断，不用‘你这是抑郁/焦虑症’这类说法。\n"
        "- 结合本次会话已有的聊天记录理解称呼、人物和事情，不要把其他会话的内容混进来；记录里没有的信息不要编造。\n"
        "- 用户问你是否知道或记得姓名、宠物、经历等信息时，先核对当前会话记录；没有明确出现就坦诚说还不知道，绝对不要猜名字或虚构共同经历。\n"
        "- 用户追问之前说过的原因、称呼或计划时，优先依据用户前面的原话回答，不要重新猜测原因或用通用安慰替代。\n"
        f"内部参考：文本分类模型给出的情绪标签是‘{emotion_label}’，"
        "仅供理解语境，不代表诊断，不要向用户复述。"
    )
    if not history:
        system_prompt += (
            "\n当前没有可用的历史聊天记录。除非用户在当前这条消息里明确提供，"
            "否则你不知道用户的姓名、宠物名或过去的安排。"
            "被问到这些信息时，请直接说‘这段对话里你还没有告诉我’，不要假装记得。"
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
    return jsonify({"status": "success", "msg": "后端服务已启动！"})


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
