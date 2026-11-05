"""Train on official train splits; select by validation macro F1; evaluate held-out test once."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import time
import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
from emotion_model import TextCNN, LABELS, LABEL_NAMES, normalize_text, tokenize, encode

ROOT = Path(__file__).resolve().parent

def dump(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def load(paths):
    rows=[]
    for p in paths:
        for row in json.loads(p.read_text(encoding='utf-8-sig')):
            if row.get('label') in LABELS and isinstance(row.get('content'),str):
                rows.append({'text':normalize_text(row['content']), 'label':row['label'], 'source':p.stem})
    return rows

def clean(rows, excluded=()):
    groups=defaultdict(list)
    for row in rows:
        if row['text']: groups[row['text']].append(row)
    conflicts={text for text,items in groups.items() if len({i['label'] for i in items})>1}
    result=[items[0] for text,items in groups.items() if text not in conflicts and text not in excluded]
    return result, {'raw':len(rows),'retained':len(result),'conflicting_texts':len(conflicts),'excluded_overlap':len(set(groups)&set(excluded))}

def evaluate(model, loader, device):
    model.eval(); ys=[]; preds=[]; loss_sum=0
    with torch.inference_mode():
        for x,y in loader:
            logits=model(x.to(device)); loss_sum+=torch.nn.functional.cross_entropy(logits,y.to(device),reduction='sum').item()
            ys.extend(y.tolist()); preds.extend(logits.argmax(dim=1).cpu().tolist())
    return {'loss':loss_sum/len(ys),'accuracy':accuracy_score(ys,preds),'macro_f1':f1_score(ys,preds,labels=list(range(6)),average='macro',zero_division=0)},ys,preds

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--epochs',type=int,default=15)
    parser.add_argument('--patience',type=int,default=3)
    parser.add_argument('--threads',type=int,default=6)
    parser.add_argument('--output',default='artifacts/emotion_cnn')
    args=parser.parse_args()
    torch.set_num_threads(args.threads); torch.set_num_interop_threads(2)
    random.seed(42); np.random.seed(42); torch.manual_seed(42)
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    out=ROOT/args.output; out.mkdir(parents=True,exist_ok=True)
    data=ROOT/'评测数据集'
    train_paths=sorted((data/'train').glob('*.txt'))
    val_paths=sorted((data/'eval（刷榜数据集）').glob('*_labeled.txt'))
    test_paths=sorted((data/'test（最终评测集）'/'真实评测集').glob('*_labeled.txt'))
    if len(train_paths)!=2 or len(val_paths)!=2 or len(test_paths)!=2: raise RuntimeError('Official dataset files missing')
    val, val_stats=clean(load(val_paths))
    train, train_stats=clean(load(train_paths),{r['text'] for r in val})
    audit={'train':train_stats,'validation':val_stats,'train_distribution':dict(Counter(r['label'] for r in train)),
           'sources':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in train_paths+val_paths},
           'policy':'Training vocabulary from train only; train/validation exact normalized overlaps removed from train; conflicting and empty training/validation texts removed; test untouched until final evaluation.'}
    dump(out/'data_audit.json',audit)
    print(json.dumps(audit,ensure_ascii=False),flush=True)
    train_tokens=[tokenize(r['text']) for r in train]
    val_tokens=[tokenize(r['text']) for r in val]
    counts=Counter(t for seq in train_tokens for t in seq)
    vocab={'<PAD>':0,'<UNK>':1}
    for t,n in counts.most_common(49998):
        if n>=2: vocab[t]=len(vocab)
    config={'model':{'vocab_size':len(vocab),'embed_dim':128,'channels':96,'kernels':[2,3,4],'dropout':.5,'num_classes':6},
            'max_len':96,'labels':LABELS,'label_names':LABEL_NAMES,'seed':42,'tokenizer':'jieba','normalizer':'NFKC + URL removal + whitespace collapse'}
    dump(out/'config.json',config); dump(out/'vocab.json',vocab)
    def loader(rows,tokens=None,shuffle=False):
        tokens=tokens if tokens is not None else [tokenize(r['text']) for r in rows]
        x=torch.tensor([encode(t,vocab,96) for t in tokens],dtype=torch.long)
        y=torch.tensor([LABELS.index(r['label']) for r in rows],dtype=torch.long)
        return DataLoader(TensorDataset(x,y),batch_size=128,shuffle=shuffle,num_workers=0)
    train_loader=loader(train,train_tokens,True); val_loader=loader(val,val_tokens)
    model=TextCNN(**config['model']).to(device)
    frequencies=np.bincount([LABELS.index(r['label']) for r in train],minlength=6)
    weights=np.sqrt(frequencies.sum()/frequencies); weights=weights/weights.mean()
    criterion=torch.nn.CrossEntropyLoss(weight=torch.tensor(weights,dtype=torch.float32,device=device))
    opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01)
    scheduler=torch.optim.lr_scheduler.ReduceLROnPlateau(opt,mode='max',factor=.5,patience=1)
    best=-1; bad=0; history=[]; start=time.perf_counter()
    print(f'Training device={device}; vocab={len(vocab)}; train={len(train)}; validation={len(val)}',flush=True)
    for epoch in range(1,args.epochs+1):
        model.train(); total=0; epoch_start=time.perf_counter()
        for step,(x,y) in enumerate(train_loader,1):
            opt.zero_grad(set_to_none=True)
            logits=model(x.to(device)); loss=criterion(logits,y.to(device)); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),5); opt.step(); total+=loss.item()*len(y)
            if step%100==0: print(f'epoch={epoch} step={step}/{len(train_loader)} loss={loss.item():.4f}',flush=True)
        metrics,_,_=evaluate(model,val_loader,device)
        row={'epoch':epoch,'train_loss':total/len(train),'validation':metrics,'seconds':round(time.perf_counter()-epoch_start,2)}
        history.append(row); print(json.dumps(row),flush=True); dump(out/'history.json',history)
        if metrics['macro_f1']>best:
            best=metrics['macro_f1']; best_epoch=epoch; bad=0
            torch.save(model.state_dict(),out/'best_model.pt')
        else: bad+=1
        scheduler.step(metrics['macro_f1'])
        if bad>=args.patience: break
    model.load_state_dict(torch.load(out/'best_model.pt',map_location=device,weights_only=True))
    test=load(test_paths)
    test_metrics,ys,preds=evaluate(model,loader(test),device)
    report={'best_epoch':best_epoch,'validation_macro_f1':best,'epochs_run':len(history),'training_seconds':round(time.perf_counter()-start,2),
            'device':str(device),'official_test':dict(test_metrics,count=len(test),
            report=classification_report(ys,preds,labels=list(range(6)),target_names=LABELS,output_dict=True,zero_division=0),
            confusion_matrix=confusion_matrix(ys,preds,labels=list(range(6))).tolist())}
    for prefix in ['usual','virus']:
        ids=[i for i,r in enumerate(test) if r['source'].startswith(prefix)]
        y=[ys[i] for i in ids]; p=[preds[i] for i in ids]
        report[prefix+'_test']={'count':len(ids),'accuracy':accuracy_score(y,p),'macro_f1':f1_score(y,p,labels=list(range(6)),average='macro',zero_division=0)}
    # Separate an exact-text-disjoint score without changing the official test score.
    seen={r['text'] for r in train+val}
    disjoint,_=clean([r for r in test if r['text'] not in seen])
    dm,_,_=evaluate(model,loader(disjoint),device)
    report['deduplicated_disjoint_test']=dict(dm,count=len(disjoint))
    dump(out/'metrics.json',report)
    with (out/'test_predictions.jsonl').open('w',encoding='utf-8') as f:
        for row,y,p in zip(test,ys,preds): f.write(json.dumps({'source':row['source'],'true':LABELS[y],'predicted':LABELS[p]},ensure_ascii=False)+'\n')
    print('TRAINING_COMPLETE '+json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__': main()
