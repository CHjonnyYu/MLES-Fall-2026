"""Support code for two individual ML Homework assignments; synthetic data only.
No network, API key, GPU, pickle or joblib is used. Review submitted Python source
before executing another student's package. Integrity hashes are not signatures.
"""
from pathlib import Path
import csv, json, hashlib, io, zipfile, tempfile, shutil, sys, subprocess, platform, html, base64, importlib.util, uuid, contextlib
import numpy as np
import sklearn, scipy
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.tree import DecisionTreeRegressor
FEATURES=['power_W','airflow_m_s','ambient_C']
COLUMNS=['run_id',*FEATURES,'temp_rise_C','split']
UNITS={'power_W':'W','airflow_m_s':'m/s','ambient_C':'degC','temp_rise_C':'degC difference'}
BASE_CONFIG={'learner':'ridge','alpha':1.0,'max_depth':3}
GROUPS={'low_airflow':lambda X:X[:,1]<=1.,'high_power':lambda X:X[:,0]>=75.,'hot_ambient':lambda X:X[:,2]>=28.}
REPORT_FIELDS=['change','prediction','result','evidence','limitations']

def digest(data):return hashlib.sha256(data).hexdigest()
def jd(data):return json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False)
def versions():return {'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'scikit-learn':sklearn.__version__}
def write_json(path,data):Path(path).write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf8')
def load_table(path,contract):
    if contract.get('units')!=UNITS:raise ValueError('unit contract mismatch; do not silently relabel or convert inputs')
    with Path(path).open(newline='',encoding='utf8') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=COLUMNS:raise ValueError('CSV columns or order differ from the declared schema')
        rows=list(reader)
    ids=[r['run_id'] for r in rows]
    if len(ids)!=len(set(ids)):raise ValueError('duplicate run_id')
    if len(rows)!=contract['rows']:raise ValueError('row count mismatch')
    numeric=[]
    for r in rows:
        try:v=[float(r[k]) for k in FEATURES+['temp_rise_C']]
        except (ValueError,TypeError):raise ValueError('non-numeric measurement') from None
        if not np.all(np.isfinite(v)):raise ValueError('non-finite measurement')
        if not (0<=v[0]<=200 and .1<=v[1]<=10 and 0<=v[2]<=60):raise ValueError('input outside declared encoding bounds')
        if r['split'] not in ['train','validation','test']:raise ValueError('unknown split label')
        numeric.append(v)
    order=np.argsort(ids);rows=[rows[i] for i in order];numeric=np.asarray(numeric)[order];ids=np.array(ids)[order]
    records=[{'run_id':r['run_id'],**{k:float(r[k]) for k in FEATURES+['temp_rise_C']},'split':r['split']} for r in rows]
    if digest(jd(records).encode())!=contract['records_sha256']:raise ValueError('ID-keyed records differ from the frozen data contract')
    split=np.array([r['split'] for r in rows]);counts={k:int(np.sum(split==k)) for k in ['train','validation','test']}
    if counts!=contract['split_counts']:raise ValueError('split counts mismatch')
    return {'ids':ids,'X':numeric[:,:3],'y':numeric[:,3],'split':split,'records_sha256':contract['records_sha256']}

def features_from_source(source):
    # This is ordinary reviewed course Python, not a sandbox for hostile code.
    scope={'np':np};exec(compile(source,'candidate_features.py','exec'),scope)
    if not callable(scope.get('candidate_features')):raise ValueError('define candidate_features(X)')
    return scope['candidate_features']
def checked_features(fn,X):
    before=X.copy();a=np.asarray(fn(X),dtype=float);b=np.asarray(fn(X),dtype=float)
    if not np.array_equal(before,X):raise ValueError('feature function changed X in place')
    if a.ndim!=2 or a.shape[0]!=len(X) or a.shape[1]<3:raise ValueError('feature shape must be rows by at least three columns')
    if not np.array_equal(a[:,:3],X):raise ValueError('preserve the three original columns first')
    if not np.all(np.isfinite(a)) or not np.array_equal(a,b):raise ValueError('features must be finite and deterministic')
    return a

def estimator(config):
    if set(config)!=set(BASE_CONFIG) or config['learner'] not in ['ridge','tree']:raise ValueError('unknown model configuration')
    alpha=config['alpha'];depth=config['max_depth']
    if not isinstance(alpha,(int,float)) or isinstance(alpha,bool) or not np.isfinite(alpha) or not (0<alpha<=1000):raise ValueError('alpha must be finite in (0,1000]')
    if not isinstance(depth,int) or isinstance(depth,bool) or not (1<=depth<=6):raise ValueError('tree depth must be an integer from 1 to 6')
    learner=Ridge(alpha=alpha,solver='svd') if config['learner']=='ridge' else DecisionTreeRegressor(max_depth=depth,min_samples_leaf=15,random_state=2031)
    return make_pipeline(StandardScaler(),learner)
def score(y,p):return {'MAE':float(np.mean(np.abs(p-y))),'RMSE':float(np.sqrt(np.mean((p-y)**2))),'n':len(y)}
def comparison(table,source,config,include_test=False):
    X,y,split=table['X'],table['y'],table['split'];tr=split=='train';va=split=='validation'
    fn=features_from_source(source);trans=checked_features(fn,X.copy())
    if config['learner']=='ridge' and config['max_depth']!=BASE_CONFIG['max_depth']:raise ValueError('max_depth has no effect on Ridge; change an active setting')
    if config['learner']=='tree' and config['alpha']!=BASE_CONFIG['alpha']:raise ValueError('alpha has no effect on this tree; retain the default unused field')
    feature_change=not(trans.shape==X.shape and np.array_equal(trans,X));model_change=config!=BASE_CONFIG
    if feature_change and model_change:raise ValueError('change the feature basis OR model settings, one factor family at a time')
    baseline=estimator(BASE_CONFIG).fit(X[tr],y[tr]);candidate=estimator(config).fit(trans[tr],y[tr])
    result={'implemented':feature_change or model_change,'versions':versions(),'validation':{'baseline':score(y[va],baseline.predict(X[va])),'candidate':score(y[va],candidate.predict(trans[va]))}}
    result['selected']='candidate' if result['validation']['candidate']['MAE']<result['validation']['baseline']['MAE'] else 'baseline'
    if include_test:
        te=split=='test';pb=baseline.predict(X[te]);pc=candidate.predict(trans[te]);result['test']={'baseline':score(y[te],pb),'candidate':score(y[te],pc)}
        result['slices']={}
        for name,group in GROUPS.items():
            mask=group(X[te])
            if mask.any():result['slices'][name]={'baseline':score(y[te][mask],pb[mask]),'candidate':score(y[te][mask],pc[mask])}
        result['test_ids']=table['ids'][te].tolist();result['predictions']={'baseline':pb.tolist(),'candidate':pc.tolist()}
    return result

def freeze_plan(path,source,config,plan,table):
    if plan.get('failure_group') not in GROUPS:raise ValueError('choose low_airflow,high_power,or hot_ambient before freezing')
    result=comparison(table,source,config)
    proposal={'source':source,'config':config,'plan':plan,'records_sha256':table['records_sha256'],'selected_on_validation':result['selected'],'validation':result['validation']}
    proposal['proposal_sha256']=digest(jd(proposal).encode());write_json(path,proposal);return proposal

def run_frozen(table,frozen,source,config,plan):
    check={k:v for k,v in frozen.items() if k!='proposal_sha256'}
    if digest(jd(check).encode())!=frozen['proposal_sha256'] or source!=frozen['source'] or config!=frozen['config'] or plan!=frozen['plan'] or table['records_sha256']!=frozen['records_sha256']:raise ValueError('proposal changed after freeze; declare a new plan and disclose any repeated test use')
    result=comparison(table,source,config,include_test=True)
    if result['selected']!=frozen['selected_on_validation']:raise ValueError('validation choice differs')
    return result

def one_page(path,title,fields,disclosure):
    # Five short sections and disclosure; this file is the separately submitted explanation.
    words=sum(len(str(v).split()) for v in fields.values())+len(str(disclosure).split())
    if words>450:raise ValueError('one-page explanation exceeds 450 words; shorten it')
    body='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>@page{size:A4;margin:18mm}body{max-width:760px;margin:20px auto;padding:12px;font:11pt/1.4 Arial;color:#12233f}h1{font-size:18pt}h2{font-size:12pt;margin:14px 0 4px}p{margin:0}footer{margin-top:18px;font-size:9pt;color:#52666b}</style><h1>'+html.escape(title)+'</h1>'
    for key in REPORT_FIELDS:body+='<h2>'+html.escape(key.title())+'</h2><p>'+html.escape(str(fields.get(key,'')).strip() or '[Complete this section]')+'</p>'
    body+='<h2>AI disclosure</h2><p>'+html.escape(str(disclosure) or '[State assistance or none]')+'</p><footer>NCKU + LAiMM · Individual Homework · Synthetic teaching case · '+str(words)+' words</footer></html>'
    Path(path).write_text(body,encoding='utf8');return words

def hw9_export(csv_path,contract,frozen,result,fields,disclosure,out_dir='hw09-output'):
    table=load_table(csv_path,contract);check=run_frozen(table,frozen,frozen['source'],frozen['config'],frozen['plan'])
    if jd(check)!=jd(result):raise ValueError('result does not match the frozen executable protocol')
    status='ready for review' if result['implemented'] and all(str(frozen['plan'].get(k,'')).strip() for k in ['hypothesis','expected','held_fixed','failure_condition']) and all(str(fields.get(k,'')).strip() for k in REPORT_FIELDS) and str(disclosure).strip() else 'draft'
    target=Path(out_dir);target.mkdir(exist_ok=True);run=target/('run-'+uuid.uuid4().hex[:10]);run.mkdir();bundle=run/'bundle';bundle.mkdir();figdir=bundle/'figures';figdir.mkdir()
    shutil.copy2(csv_path,bundle/'frozen.csv');write_json(bundle/'contract.json',contract);write_json(bundle/'experiment.json',frozen);write_json(bundle/'result.json',result);write_json(bundle/'environment.json',versions());(bundle/'candidate_features.py').write_text(frozen['source']);shutil.copy2(Path(__file__),bundle/'hw_workflow.py')
    with (bundle/'reference-predictions.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['run_id','baseline','candidate'])
        writer.writerows(zip(result['test_ids'],result['predictions']['baseline'],result['predictions']['candidate']))
    replay="from pathlib import Path\nimport json,sys\nfrom hw_workflow import replay_directory\nif __name__=='__main__':\n    result=replay_directory(Path(__file__).parent)\n    print(json.dumps(result,indent=2))\n"
    (bundle/'replay.py').write_text(replay)
    (bundle/'requirements.txt').write_text('\n'.join(k+'=='+v for k,v in versions().items() if k!='python')+'\n')
    (bundle/'README.txt').write_text('Inspect the Python source first. Use CPU and the recorded package versions. Run: python replay.py\nThis is a reviewed class package, not a sandbox. A new process is not automatically an independent person or environment.\nThe receiver compares every ID-aligned baseline and candidate test prediction with atol=1e-8,rtol=1e-10. Do not change the frozen selection from test scores.\n')
    import matplotlib.pyplot as plt
    X,y,split=table['X'],table['y'],table['split'];te=split=='test'
    fig,axes=plt.subplots(1,2,figsize=(10,4),sharex=True,sharey=True)
    for ax,kind in zip(axes,['baseline','candidate']):ax.scatter(X[te,1],np.asarray(result['predictions'][kind])-y[te],s=20);ax.axhline(0,c='black',lw=1);ax.set(title=kind,xlabel='airflow (m/s)',ylabel='prediction - observation (degC)')
    fig.tight_layout();fig.savefig(figdir/'residuals.png',dpi=140);plt.show();plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,4));ax.bar(['baseline','candidate'],[result['test'][k]['MAE'] for k in ['baseline','candidate']]);ax.set(ylabel='test MAE (degC)',title='Predeclared diagnosis; selection was frozen on validation');fig.tight_layout();fig.savefig(figdir/'comparison.png',dpi=140);plt.show();plt.close(fig)
    words=one_page(run/'HW9-explanation.html','HW9 · Diagnose and defend a change',fields,disclosure);shutil.copy2(run/'HW9-explanation.html',bundle/'explanation.html')
    gallery='<!doctype html><html lang="en"><meta charset="utf-8"><title>HW9 evidence</title><style>body{max-width:1000px;margin:auto;font:18px/1.5 sans-serif}img{max-width:100%}pre{white-space:pre-wrap}</style><h1>HW9 evidence: '+status+'</h1><pre>'+html.escape(json.dumps({'validation':result['validation'],'test':result['test'],'slices':result['slices']},indent=2))+'</pre>'
    for file in sorted(figdir.glob('*.png')):gallery+='<h2>'+file.stem+'</h2><img alt="'+file.stem+'" src="data:image/png;base64,'+base64.b64encode(file.read_bytes()).decode()+'">'
    (bundle/'evidence-report.html').write_text(gallery)
    manifest={'assignment':'HW9','status':status,'scope':'Synthetic individual experiment; presence is not correctness.','files':{str(p.relative_to(bundle)):digest(p.read_bytes()) for p in sorted(bundle.rglob('*')) if p.is_file()}}
    write_json(bundle/'manifest.json',manifest)
    package=run/'hw09-evidence.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(bundle.rglob('*')):
            if p.is_file():z.write(p,str(p.relative_to(bundle)))
    print('HW9:',status,'\nEvidence ZIP:',package,'\nSeparate one-page explanation:',run/'HW9-explanation.html','\nWords:',words)
    return {'status':status,'zip':str(package.resolve()),'explanation':str((run/'HW9-explanation.html').resolve()),'bundle':str(bundle.resolve())}

def validate_manifest(folder):
    folder=Path(folder);m=json.loads((folder/'manifest.json').read_text())
    for name,h in m['files'].items():
        p=Path(name)
        if p.is_absolute() or '..' in p.parts:raise ValueError('unsafe manifest path')
        if not (folder/name).is_file() or digest((folder/name).read_bytes())!=h:raise ValueError('file checksum mismatch: '+name)
    return m

def unpack(package,destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(package) as z:
        if sum(i.file_size for i in z.infolist())>20_000_000:raise ValueError('class package exceeds 20 MB')
        for i in z.infolist():
            p=Path(i.filename)
            if p.is_absolute() or '..' in p.parts or ((i.external_attr>>16)&0o170000)==0o120000:raise ValueError('unsafe ZIP path or symlink')
        z.extractall(destination)
    validate_manifest(destination);return destination

def replay_directory(folder):
    folder=Path(folder);m=validate_manifest(folder)
    if m['status']!='ready for review':raise ValueError('HW9 package is a draft; finish your actual change and explanation first')
    contract=json.loads((folder/'contract.json').read_text());table=load_table(folder/'frozen.csv',contract);frozen=json.loads((folder/'experiment.json').read_text())
    if (folder/'candidate_features.py').read_text()!=frozen['source']:raise ValueError('feature source differs from frozen declaration')
    result=run_frozen(table,frozen,frozen['source'],frozen['config'],frozen['plan'])
    with (folder/'reference-predictions.csv').open() as f:records=list(csv.DictReader(f))
    ids=[r['run_id'] for r in records]
    if len(ids)!=len(set(ids)) or set(ids)!=set(result['test_ids']):raise ValueError('reference prediction IDs mismatch')
    by_id={r['run_id']:r for r in records};differences={}
    for name in ['baseline','candidate']:
        expected=np.array([float(by_id[i][name]) for i in result['test_ids']]);actual=np.array(result['predictions'][name])
        if not np.allclose(actual,expected,rtol=1e-10,atol=1e-8):raise ValueError('prediction vector mismatch for '+name)
        differences[name]=float(np.max(np.abs(actual-expected)))
    return {'status':'reproduced','rows_compared':len(ids),'max_abs_difference':differences,'atol':1e-8,'rtol':1e-10,'selected_on_validation':result['selected'],'receiver_versions':versions(),'sender_versions':json.loads((folder/'environment.json').read_text()),'scope':'New Python process in receiver working directory; independence requires a separate human receiver.'}

def fresh_process_replay(package,destination):
    folder=unpack(package,destination)
    process=subprocess.run([sys.executable,str((folder/'replay.py').resolve())],cwd=folder,capture_output=True,text=True,timeout=60)
    receipt={'returncode':process.returncode,'stdout':process.stdout,'stderr':process.stderr,'command':'python replay.py','fresh_process':True}
    if process.returncode==0:receipt['result']=json.loads(process.stdout)
    return folder,receipt

def negative_test(folder,mutate_contract):
    contract=json.loads((Path(folder)/'contract.json').read_text());before=jd(contract);bad=json.loads(before);mutate_contract(bad)
    if jd(bad)==before:return {'status':'not implemented','expected_rejection':False}
    try:load_table(Path(folder)/'frozen.csv',bad)
    except ValueError as e:return {'status':'rejected','expected_rejection':True,'exception':type(e).__name__,'message':str(e)}
    return {'status':'unexpectedly accepted','expected_rejection':False}

def hw10_export(receipt,rejection,fields,disclosure,verification_mode,receiver_status,history=None,package_path=None,out_dir='hw10-output'):
    if verification_mode not in ['peer','self-replay']:raise ValueError('mode must honestly be peer or self-replay')
    if verification_mode=='peer' and not str(receiver_status).strip():raise ValueError('describe the actual independent receiver and action; a mode label is not evidence')
    complete=receipt.get('returncode')==0 and rejection.get('expected_rejection') and all(str(fields.get(k,'')).strip() for k in REPORT_FIELDS) and str(disclosure).strip() and str(receiver_status).strip()
    status=('ready for review' if verification_mode=='peer' else 'self-replay; instructor/TA verification pending') if complete else 'draft or unresolved replay failure'
    out=Path(out_dir)/('run-'+uuid.uuid4().hex[:10]);out.mkdir(parents=True);write_json(out/'replay-receipt.json',receipt);write_json(out/'negative-test.json',rejection);write_json(out/'verification.json',{'mode':verification_mode,'receiver_status':receiver_status,'status':status,'AI_disclosure':disclosure,'presence_is_not_correctness':True});write_json(out/'receiver-environment.json',versions());one_page(out/'HW10-explanation.html','HW10 · Handover and reproducibility',fields,disclosure)
    write_json(out/'replay-history.json',history or [receipt])
    if package_path is not None and Path(package_path).is_file():write_json(out/'package-identity.json',{'filename':Path(package_path).name,'sha256':digest(Path(package_path).read_bytes())})
    files=sorted(p for p in out.iterdir() if p.is_file());write_json(out/'manifest.json',{'status':status,'files':{p.name:digest(p.read_bytes()) for p in files}})
    package=out/'hw10-evidence.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.iterdir()):
            if p.is_file() and p!=package:z.write(p,p.name)
    print('HW10:',status,'\nEvidence ZIP:',package,'\nSeparate one-page explanation:',out/'HW10-explanation.html')
    return {'status':status,'zip':str(package.resolve()),'explanation':str((out/'HW10-explanation.html').resolve())}
