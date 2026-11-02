"""A real pretrained LLM selects actions; pure local tools supply the numbers."""
from pathlib import Path
import json,hashlib,time
MODEL='HuggingFaceTB/SmolLM2-135M-Instruct'
REVISION='12fd25f77366fa6b3b4b768ec3050bf629380bac'
DATA={'case':'synthetic packaging temperature inspection','unit':'degC','temperature':[72.,81.,79.,85.,80.,74.]}
GOAL='Report the maximum temperature and the count of measurements at or above 80 degC. Use tools, then finish.'
ACTIONS={'max_temperature':{'tool':'max_temperature','args':{}},'count_at_or_above':{'tool':'count_at_or_above','args':{'threshold':80.0}},'inspect_schema':{'tool':'inspect_schema','args':{}},'finish':{'tool':'finish','args':{}}}
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()
def dispatch(a,data):
 if a not in list(ACTIONS.values()):raise ValueError('Unknown action or arguments')
 t=a['tool']
 if t=='max_temperature':return {'maximum':max(data['temperature']),'unit':data['unit']}
 if t=='count_at_or_above':return {'count':sum(v>=a['args']['threshold'] for v in data['temperature']),'threshold':80.0,'rows':len(data['temperature'])}
 if t=='inspect_schema':return {'case':data['case'],'unit':data['unit'],'rows':len(data['temperature'])}
 raise ValueError('unreachable')
def run(mode='replay',trace_path='agent-live-trace.json',data=DATA):
 if mode not in ['live','replay']:raise ValueError('mode must be live or replay')
 if data['unit']!='degC' or not data['temperature']:raise ValueError('Expected nonempty degC observations')
 tracefile=Path(trace_path)
 if mode=='live':
  import torch
  from transformers import AutoModelForCausalLM,AutoTokenizer
  torch.set_num_threads(4)
  tok=AutoTokenizer.from_pretrained(MODEL,revision=REVISION)
  llm=AutoModelForCausalLM.from_pretrained(MODEL,revision=REVISION).to('cpu').eval()
  token_ids=[tok.encode(c,add_special_tokens=False) for c in ['A','B','C']]
  assert all(len(t)==1 for t in token_ids),'Menu labels must each be a single token.'
 else:
  saved=json.loads(tracefile.read_text());assert saved['input_sha256']==digest(data) and saved['goal']==GOAL,'Replay input/goal differs; run live for new decisions.'
 observations={};steps=[];previous=[];start=time.time()
 for turn in range(4):
  ready=all(k in observations for k in ['max_temperature','count_at_or_above'])
  candidates=['finish'] if ready else [k for k in ['max_temperature','count_at_or_above','inspect_schema'] if k not in observations]
  prompt='You are a tool-using assistant. Choose the next permitted tool. Respond with one letter only.\nTask: '+GOAL+'\nKnown observations: '+json.dumps(observations)+'\nAvailable actions:\n'+'\n'.join(chr(65+i)+': '+json.dumps(ACTIONS[k]) for i,k in enumerate(candidates))+'\nNext action letter:'
  if mode=='live':
   formatted=tok.apply_chat_template([{'role':'user','content':prompt}],tokenize=False,add_generation_prompt=True)
   encoded=tok(formatted,return_tensors='pt')
   with torch.inference_mode():
    logits=llm(**encoded).logits[0,-1];scores=[float(logits[token_ids[i][0]]) for i in range(len(candidates))]
   chosen=int(max(range(len(scores)),key=scores.__getitem__))
  else:
   old=saved['steps'][turn];assert old['prompt_sha256']==digest(prompt) and old['candidates']==candidates
   chosen=old['choice'];scores=old['allowed_token_logits']
  action=ACTIONS[candidates[chosen]]
  # Controller allows only known tools, validated fixed arguments and no repeated evidence calls.
  if action['tool']=='finish':
   assert ready
   observation={'maximum':observations['max_temperature']['maximum'],'count_at_or_above_80':observations['count_at_or_above']['count']}
  else:observation=dispatch(action,data);observations[action['tool']]=observation
  step={'turn':turn,'candidates':candidates,'choice':chosen,'action':action,'observation':observation,'prompt_sha256':digest(prompt),'allowed_token_logits':scores}
  if mode=='replay':assert step==saved['steps'][turn],'Replay tool observation differs'
  steps.append(step);print(mode.upper(),turn,action,'→',observation)
  if action['tool']=='finish':break
 else:raise RuntimeError('Budget exhausted without a supported answer')
 report={'mode':mode,'model':MODEL,'model_revision':REVISION,'goal':GOAL,'input_sha256':digest(data),'steps':steps,'final':observation,'elapsed_seconds':round(time.time()-start,3),'method':'Pretrained causal-LM next-token logits select a constrained action letter; no hand-authored action sequence or paid API. Tools, not generated prose, supply final numeric fields.'}
 assert report['final']=={'maximum':max(data['temperature']),'count_at_or_above_80':sum(v>=80 for v in data['temperature'])}
 if mode=='live':tracefile.write_text(json.dumps(report,indent=2))
 return report
