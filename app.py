from flask import Flask, request, jsonify
from flask_cors import CORS
import pymysql
import requests
import torch
import torch.nn as nn
import jieba
import pickle

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
with open("word2id.pkl", "rb") as f:
    word2id = pickle.load(f)
vocab_size = len(word2id)

device = torch.device("cpu")
emotion_model = TextCNN(vocab_size, embed_dim=100, num_classes=5).to(device)
emotion_model.load_state_dict(torch.load("textcnn_model.pth", map_location=device))
emotion_model.eval()  # 切换到推理模式

id2label = {0: "快乐", 1: "焦虑", 2: "悲伤", 3: "愤怒", 4: "压力大"}
MAX_LEN = 20


def predict_emotion(text):
    """对输入的文本进行情绪预测"""
    tokens = [word for word in jieba.cut(text)]
    seq = [word2id.get(word, 1) for word in tokens]  # 1 是 <UNK>
    seq_padded = seq[:MAX_LEN] + [0] * (MAX_LEN - len(seq))  # 补齐

    tensor_x = torch.tensor([seq_padded], dtype=torch.long).to(device)
    with torch.no_grad():
        outputs = emotion_model(tensor_x)
        probabilities = torch.softmax(outputs, dim=1)
        confidence, predicted = torch.max(probabilities, 1)

    return id2label[predicted.item()], confidence.item()


print("模型加载完毕！")


# ==========================================
# 3. 数据库连接与大模型调用
# ==========================================
def get_db_conn():
    return pymysql.connect(
        host="127.0.0.1", port=3306, user="root",
        password="230525txP.",  # ⚠️ 替换为你自己的密码
        database="psych_db", charset="utf8mb4"
    )


def ask_ollama(user_text, emotion_label):
    system_prompt = (
        "你是一个温暖、有共情力的心理陪伴者。"
        "用户正在向你倾诉，请用温和、支持性的语气回复，"
        "不要给出医学诊断，不要评判用户。"
        f"当前识别到的情绪倾向是：{emotion_label}。"
    )
    try:
        response = requests.post(
            "http://localhost:11434/v1/chat/completions",
            json={
                "model": "qwen2.5:7b",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ],
                "stream": False
            },
            timeout=60
        )
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("调用 Ollama 失败:", e)
        return "抱歉，我暂时无法回应，但我在这里陪着你。"


# ==========================================
# 4. 接口路由
# ==========================================
@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({"status": "success", "msg": "后端服务已启动！"})


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_text = data.get('text', '')
    user_id = data.get('user_id', 'test_user')

    if not user_text:
        return jsonify({"status": "error", "msg": "文本不能为空"}), 400

    # 🌟 核心替换：真正调用模型预测情绪
    emotion_label, confidence = predict_emotion(user_text)
    print(f"用户输入: {user_text} | 预测情绪: {emotion_label} | 置信度: {confidence:.2f}")

    # 调用大模型生成回复
    reply = ask_ollama(user_text, emotion_label)

    # 写入数据库
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        sql = "INSERT INTO emotion_record (user_id, user_text, emotion_label, confidence, llm_reply) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(sql, (user_id, user_text, emotion_label, confidence, reply))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print("写入数据库失败:", e)

    return jsonify({
        "status": "success",
        "emotion_label": emotion_label,
        "confidence": confidence,
        "reply": reply
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)