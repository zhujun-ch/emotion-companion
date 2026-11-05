import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import jieba
import pandas as pd
from sklearn.model_selection import train_test_split
import numpy as np

# ==========================================
# 1. 数据预处理与词表构建
# ==========================================
# 这里为了演示，我们写死几条数据，实际应用中你可以读 pd.read_csv('train.csv')
data = [
    ("我今天太开心了，拿到了奖学金", "快乐"),
    ("明天要考试了，我什么都还没背，好焦虑", "焦虑"),
    ("他为什么这样对我，我真的很生气", "愤怒"),
    ("连续加了一个星期的班，好累，感觉身体被掏空", "压力大"),
    ("我失恋了，每天都在哭，感觉好难过", "悲伤"),
    ("终于放假了，准备出去玩，心情超级好", "快乐"),
    ("马上就要答辩了，好紧张，怕过不了", "焦虑"),
    ("室友总是半夜打游戏，我真的要气炸了", "愤怒"),
    ("作业太多了，根本写不完，压得我喘不过气", "压力大"),
    ("感觉没人理解我，一个人在角落很孤独", "悲伤")
]

# 扩充数据（复制刚才的数据，凑够 100 条以便能跑起来）
data = data * 10

texts = [item[0] for item in data]
labels = [item[1] for item in data]

# 构建标签映射
label2id = {"快乐": 0, "焦虑": 1, "悲伤": 2, "愤怒": 3, "压力大": 4}
id2label = {v: k for k, v in label2id.items()}
y = [label2id[l] for l in labels]

# 分词并构建词表
tokenized_texts = [[word for word in jieba.cut(text)] for text in texts]
word2id = {"<PAD>": 0, "<UNK>": 1}
for tokens in tokenized_texts:
    for word in tokens:
        if word not in word2id:
            word2id[word] = len(word2id)

# 转化为 ID
X = [[word2id.get(word, 1) for word in tokens] for tokens in tokenized_texts]

# 统一长度（截断或补齐）
MAX_LEN = 20
X_padded = [seq[:MAX_LEN] + [0] * (MAX_LEN - len(seq)) for seq in X]

# 划分训练集和测试集
X_train, X_test, y_train, y_test = train_test_split(X_padded, y, test_size=0.2, random_state=42)


# ==========================================
# 2. 构建 Dataset
# ==========================================
class TextDataset(Dataset):
    def __init__(self, X, y):
        self.X = torch.tensor(X, dtype=torch.long)
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


train_loader = DataLoader(TextDataset(X_train, y_train), batch_size=8, shuffle=True)
test_loader = DataLoader(TextDataset(X_test, y_test), batch_size=8)


# ==========================================
# 3. 定义 TextCNN 模型
# ==========================================
class TextCNN(nn.Module):
    def __init__(self, vocab_size, embed_dim, num_classes):
        super(TextCNN, self).__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        # 卷积层：提取2元、3元、4元词组特征
        self.conv1 = nn.Conv2d(1, 100, (2, embed_dim))
        self.conv2 = nn.Conv2d(1, 100, (3, embed_dim))
        self.conv3 = nn.Conv2d(1, 100, (4, embed_dim))
        self.dropout = nn.Dropout(0.5)
        self.fc = nn.Linear(300, num_classes)

    def forward(self, x):
        x = self.embedding(x)  # [batch, seq_len, embed_dim]
        x = x.unsqueeze(1)  # [batch, 1, seq_len, embed_dim]

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
# 4. 训练与评估
# ==========================================
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
vocab_size = len(word2id)
model = TextCNN(vocab_size, embed_dim=100, num_classes=5).to(device)

criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=0.001)

print(f"开始训练 TextCNN (设备: {device})...")
epochs = 10
for epoch in range(epochs):
    model.train()
    total_loss = 0
    for batch_X, batch_y in train_loader:
        batch_X, batch_y = batch_X.to(device), batch_y.to(device)
        optimizer.zero_grad()
        outputs = model(batch_X)
        loss = criterion(outputs, batch_y)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    print(f"Epoch {epoch + 1}/{epochs}, Loss: {total_loss / len(train_loader):.4f}")

# 保存模型和词表
torch.save(model.state_dict(), "textcnn_model.pth")
import pickle

with open("word2id.pkl", "wb") as f:
    pickle.dump(word2id, f)

print("模型训练完成！已保存 textcnn_model.pth 和 word2id.pkl")