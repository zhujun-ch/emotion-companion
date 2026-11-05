"""Shared TextCNN preprocessing, architecture, and inference bundle."""
import json
import re
import unicodedata
from pathlib import Path
import jieba
import torch
from torch import nn
import torch.nn.functional as F

LABELS = ['angry', 'fear', 'happy', 'neutral', 'sad', 'surprise']
LABEL_NAMES = ['愤怒', '恐惧', '快乐', '中性', '悲伤', '惊奇']

def normalize_text(text):
    text = unicodedata.normalize('NFKC', text)
    return re.sub(r'\s+', ' ', re.sub(r'https?://\S+', ' ', text)).strip()

def tokenize(text):
    return [x for x in jieba.lcut(normalize_text(text)) if x.strip()]

def encode(tokens, vocab, max_len):
    ids = [vocab.get(t, 1) for t in tokens[:max_len]]
    return ids + [0] * (max_len - len(ids))

class TextCNN(nn.Module):
    def __init__(self, vocab_size, embed_dim=128, channels=96, kernels=(2,3,4), dropout=.5, num_classes=6, **kwargs):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.convs = nn.ModuleList([nn.Conv1d(embed_dim, channels, k) for k in kernels])
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(channels * len(kernels), num_classes)
    def forward(self, x):
        x = self.embedding(x).transpose(1,2)
        features = [F.relu(conv(x)).amax(dim=2) for conv in self.convs]
        return self.fc(self.dropout(torch.cat(features,dim=1)))

class EmotionPredictor:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.config = json.loads((self.directory/'config.json').read_text(encoding='utf-8'))
        self.vocab = json.loads((self.directory/'vocab.json').read_text(encoding='utf-8'))
        self.model = TextCNN(**self.config['model'])
        self.model.load_state_dict(torch.load(self.directory/'best_model.pt', map_location='cpu', weights_only=True))
        self.model.eval()
    def predict(self, text):
        x = torch.tensor([encode(tokenize(text),self.vocab,self.config['max_len'])],dtype=torch.long)
        with torch.inference_mode():
            probs = self.model(x).softmax(dim=1)[0]
        score, label = probs.max(dim=0)
        return self.config['label_names'][label.item()], score.item()
