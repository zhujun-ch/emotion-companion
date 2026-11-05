import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import app as backend
from conversation_store import ConversationStore
from emotion_reference import EmotionReference

LABELS=['愤怒','恐惧','快乐','中性','悲伤','惊奇']
def distribution(label, value=.9):
    p=[(1-value)/5]*6; p[label]=value; return p

def policy(mapping):
    obj=EmotionReference.__new__(EmotionReference)
    obj.calibration={'temperature':1.2,'thresholds':[.7,.7,.7,.7,.7,None]}
    obj.predictor=SimpleNamespace(config={'label_names':LABELS},probabilities=lambda text,temp: mapping[text])
    return obj

class ReferenceTests(unittest.TestCase):
    def test_first_three_do_not_predict_or_inject_a_label(self):
        p=policy({})
        for n in range(1,4):
            r=p.assess([], '很难过', n)
            self.assertEqual(r['state'],'collecting'); self.assertIsNone(r['label'])

    def test_ready_only_with_recent_agreement_and_strong_scores(self):
        p=policy({t:distribution(2) for t in ['一','二','三','四']})
        r=p.assess(['一','二','三'],'四',4)
        self.assertEqual(r['state'],'ready'); self.assertEqual(r['label'],'快乐')
        p.predictor.probabilities=lambda t,temp: distribution(2,.4)
        self.assertEqual(p.assess(['一','二','三'],'四',4)['state'],'uncertain')

    def test_change_and_backchannels_do_not_get_forced_labels(self):
        p=policy({'一':distribution(2),'二':distribution(2),'三':distribution(2),'四':distribution(4)})
        self.assertEqual(p.assess(['一','二','三'],'四',4)['state'],'changing')
        self.assertEqual(p.assess(['一','二','三'],'嗯嗯',4)['state'],'insufficient')
        p.predictor.probabilities=lambda t,temp: distribution(5)
        self.assertEqual(p.assess(['一','二','三'],'四',4)['state'],'uncertain')
        p.calibration=None
        self.assertEqual(p.assess(['一','二','三'],'四',4)['state'],'uncertain')

    def test_disagreement_still_exposes_uncertain_candidates(self):
        p=policy({'一':distribution(2),'二':distribution(2),'三':distribution(3),'四':distribution(4)})
        result=p.assess(['一','二','三'],'四',4)
        self.assertEqual(len(result['candidates']),2)
        self.assertIsNone(result['label'])
        self.assertEqual(result['state'],'changing')

    def test_two_recent_votes_can_support_reference(self):
        p=policy({'一':distribution(4),'二':distribution(4),'三':distribution(2),'四':distribution(4)})
        result=p.assess(['一','二','三'],'四',4)
        self.assertEqual(result['state'],'ready')
        self.assertEqual(result['label'],'悲伤')

    def test_feedback_snapshot_persistence_and_ownership(self):
        with tempfile.TemporaryDirectory() as d:
            store=ConversationStore(Path(d)/'db.sqlite3')
            with patch.object(backend,'conversation_store',store), patch.object(backend,'emotion_reference_policy',policy({t:distribution(2) for t in ['一','二','三','四']})), patch.object(backend,'predict_emotion',return_value=('快乐',.9)), patch.object(backend,'ask_ollama',return_value='在听你说。') as model:
                c=backend.app.test_client(); user='reference_owner'
                sid=c.post('/api/sessions',json={'user_id':user}).json['session']['id']
                for i,text in enumerate(['一','二','三','四'],1):
                    response=c.post('/api/chat',json={'user_id':user,'session_id':sid,'text':text})
                    self.assertEqual(response.status_code,200)
                    expected=None if i<=3 else '快乐'
                    self.assertEqual(model.call_args.args[1],expected)
                    self.assertEqual(response.json['emotion_reference']['label'],expected)
                mid=response.json['assistant_message_id']
                url=f'/api/messages/{mid}/feedback'
                self.assertEqual(c.post(url,json={'user_id':'other','agreed':False}).status_code,404)
                self.assertEqual(c.post(url,json={'user_id':user,'agreed':False,'correction':'抑郁症'}).status_code,400)
                self.assertEqual(c.post(url,json={'user_id':user,'agreed':'false'}).status_code,400)
                r=c.post(url,json={'user_id':user,'agreed':False,'correction':'悲伤'})
                self.assertEqual(r.status_code,200)
                restored=ConversationStore(store.path).messages(sid)[-1]
                self.assertEqual(restored['emotion_reference']['state'],'ready')
                self.assertEqual(restored['feedback']['correction'],'悲伤')
                self.assertEqual(restored['emotion'],'快乐')  # Feedback does not overwrite raw model output.
                self.assertEqual(c.delete(f'/api/sessions/{sid}?user_id={user}').status_code,200)
                with store.connect() as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM emotion_feedback').fetchone()[0],0)

    def test_prompt_omits_unqualified_single_sentence_label(self):
        fake=SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'choices':[{'message':{'content':'在听。'}}]})
        with patch.object(backend.requests,'post',return_value=fake) as post:
            backend.ask_ollama('有点累',None,[])
            prompt=post.call_args.kwargs['json']['messages'][0]['content']
            self.assertNotIn('情绪倾向是',prompt)
            self.assertIn('不预设',prompt)

if __name__=='__main__': unittest.main()
