"""Conservative conversation reference; pooled scores are not probabilities of mood."""
import hashlib
import json
import re
from pathlib import Path

ACKNOWLEDGEMENTS = {'嗯','嗯嗯','哦','噢','好','好的','知道了','谢谢','是的','对','对的','哈哈','嗯哼','行','收到'}


def meaningful(text):
    stripped = re.sub(r'[\W_]+', '', text)
    return bool(stripped) and stripped not in ACKNOWLEDGEMENTS


class EmotionReference:
    def __init__(self, predictor):
        self.predictor = predictor
        path = predictor.directory / 'calibration.json'
        self.calibration = None
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            digest = hashlib.sha256((predictor.directory / 'best_model.pt').read_bytes()).hexdigest()
            if data.get('checkpoint_sha256') == digest:
                self.calibration = data

    def assess(self, previous_user_texts, current_text, turn_count):
        base = {'version':2, 'label':None, 'candidates':[], 'turn_count':turn_count, 'evidence_count':0,
                'state':'collecting', 'reason':'先聊聊，暂不判断情绪'}
        # The first three user messages are a warm-up, not a diagnostic questionnaire.
        if turn_count <= 3:
            return base
        texts = [t for t in previous_user_texts[-4:] + [current_text] if meaningful(t)]
        base['evidence_count'] = len(texts)
        if not meaningful(current_text) or len(texts) < 3:
            return dict(base, state='insufficient', reason='表达信息还不够，先继续聊聊')
        if self.calibration is None:
            return dict(base, state='uncertain', reason='暂不判断，分数校准尚未就绪')
        probs = [self.predictor.probabilities(t, self.calibration['temperature']) for t in texts]
        # Most recent expressions matter more; no assistant utterances enter this pool.
        weights = list(range(1,len(probs)+1))
        pooled = [sum(w*p[k] for w,p in zip(weights,probs))/sum(weights) for k in range(len(probs[0]))]
        candidate = max(range(len(pooled)), key=pooled.__getitem__)
        winners = [max(range(len(p)),key=p.__getitem__) for p in probs]
        candidates = [self.predictor.config['label_names'][k] for k in sorted(range(len(pooled)),key=pooled.__getitem__,reverse=True)[:2]]
        base['candidates'] = candidates
        if winners[-1] != candidate or winners[-3:].count(candidate) < 2:
            return dict(base, state='changing', reason='已分析近期表达，但不同句子的判断不一致，以下仅为初步方向')
        threshold = self.calibration['thresholds'][candidate]
        if threshold is None:
            return dict(base, state='uncertain', reason='已完成分析，这类表达的判断把握较低')
        strong = sum(w==candidate and p[candidate]>=threshold for w,p in zip(winners[-3:],probs[-3:]))
        if probs[-1][candidate] < threshold or strong < 2:
            return dict(base, state='uncertain', reason='已完成分析，判断把握较低，以下仅为初步方向')
        return dict(base, state='ready', label=self.predictor.config['label_names'][candidate],
                    reason='仅参考近期文字表达，不代表对你的确定判断')
