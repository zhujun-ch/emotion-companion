"""Fit temperature on half of validation; choose class thresholds on the other half."""
import hashlib,json,math
from pathlib import Path
import numpy as np
import torch
from scipy.optimize import minimize_scalar
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader,TensorDataset
from emotion_model import EmotionPredictor,LABELS,tokenize,encode
from train_textcnn import load,clean

root=Path(__file__).resolve().parent
out=root/'artifacts/emotion_cnn'
torch.set_num_threads(4)
predictor=EmotionPredictor(out)
rows,_=clean(load(sorted((root/'评测数据集/eval（刷榜数据集）').glob('*_labeled.txt'))))
x=torch.tensor([encode(tokenize(r['text']),predictor.vocab,predictor.config['max_len']) for r in rows],dtype=torch.long)
y=np.array([LABELS.index(r['label']) for r in rows])
logits=[]
with torch.inference_mode():
 for (batch,) in DataLoader(TensorDataset(x),batch_size=128): logits.append(predictor.model(batch))
logits=torch.cat(logits).numpy()
fit,select=train_test_split(np.arange(len(y)),test_size=.5,stratify=y,random_state=71)
def probs(a,t):
 z=a/t; z-=z.max(axis=1,keepdims=True); p=np.exp(z); return p/p.sum(axis=1,keepdims=True)
def nll(ids,t):
 p=probs(logits[ids],t); return float(-np.log(p[np.arange(len(ids)),y[ids]].clip(1e-12)).mean())
temp=math.exp(minimize_scalar(lambda l:nll(fit,math.exp(l)),bounds=(-2,3),method='bounded').x)
p=probs(logits[select],temp); pred=p.argmax(1); score=p.max(1); correct=pred==y[select]
thresholds=[]; details=[]
for k,label in enumerate(LABELS):
 ids=np.where(pred==k)[0]; ids=ids[np.argsort(-score[ids])]
 candidates=[]
 for n in range(20,len(ids)+1):
  threshold=float(score[ids[n-1]])
  chosen=ids[score[ids]>=threshold]
  precision=float(correct[chosen].mean())
  if precision>=.80: candidates.append((len(chosen),threshold,precision))
 if candidates:
  n,t,precision=max(candidates,key=lambda a:a[0]); thresholds.append(t)
  details.append({'label':label,'threshold':t,'selected':n,'precision':precision})
 else:
  thresholds.append(None); details.append({'label':label,'threshold':None,'selected':0,'precision':None})
result={'checkpoint_sha256':hashlib.sha256((out/'best_model.pt').read_bytes()).hexdigest(),'temperature':temp,'thresholds':thresholds,
 'class_details':details,'fit_count':len(fit),'threshold_selection_count':len(select),'target_precision':.8,'minimum_selected_per_class':20,
 'selection_nll_before':nll(select,1),'selection_nll_after':nll(select,temp),
 'scope':'Validation-only exploratory calibration; validation previously used for model selection. No test tuning. Threshold performance is not a guarantee on chat data; multi-message pooling is a heuristic, not calibrated conversation accuracy.'}
(out/'calibration.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
