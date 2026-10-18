"""Deploy MLES to Cloud Run. Credentials are read privately and sent via stdin."""
from pathlib import Path
import argparse,json,os,subprocess,sys,time

parser=argparse.ArgumentParser()
parser.add_argument('--project',required=True)
parser.add_argument('--region',default='asia-east1')
parser.add_argument('--gcloud',default='gcloud')
parser.add_argument('--initialize',action='store_true')
parser.add_argument('--private-config',default=str(Path.home()/'.config/mles-course/local-secrets.json'))
args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1]
project,region=args.project,args.region
bucket=project+'-content'
runtime='mles-runtime@'+project+'.iam.gserviceaccount.com'
builder='mles-builder@'+project+'.iam.gserviceaccount.com'

def call(parts,input_value=None,check=True):
    command=[args.gcloud,*parts,'--quiet']
    result=subprocess.run(command,input=input_value,text=True,capture_output=True,cwd=ROOT)
    # Newly created service-account identities can take a moment to propagate to IAM.
    for attempt in range(5):
        if not (result.returncode and 'Service account ' in result.stderr and 'does not exist' in result.stderr):break
        time.sleep(5)
        result=subprocess.run(command,input=input_value,text=True,capture_output=True,cwd=ROOT)
    if check and result.returncode:
        print(result.stderr,file=sys.stderr)
        raise SystemExit(result.returncode)
    return result

if args.initialize:
    call(['services','enable','run.googleapis.com','cloudbuild.googleapis.com','artifactregistry.googleapis.com','secretmanager.googleapis.com','storage.googleapis.com','--project='+project])
    for name in ['mles-runtime','mles-builder']:
        if call(['iam','service-accounts','describe',name+'@'+project+'.iam.gserviceaccount.com','--project='+project],check=False).returncode:
            call(['iam','service-accounts','create',name,'--display-name=MLES '+name,'--project='+project])
    call(['projects','add-iam-policy-binding',project,'--member=serviceAccount:'+builder,'--role=roles/run.builder'])
    if call(['storage','buckets','describe','gs://'+bucket,'--project='+project],check=False).returncode:
        call(['storage','buckets','create','gs://'+bucket,'--location='+region,'--uniform-bucket-level-access','--public-access-prevention','--project='+project])
    call(['storage','buckets','update','gs://'+bucket,'--versioning','--project='+project])
    call(['storage','buckets','add-iam-policy-binding','gs://'+bucket,'--member=serviceAccount:'+runtime,'--role=roles/storage.objectAdmin','--project='+project])
    private=json.loads(Path(args.private_config).read_text())
    for name,key in [('mles-session-key','session_secret'),('mles-admin-password-hash','admin_password_hash')]:
        existing=call(['secrets','describe',name,'--project='+project],check=False)
        if existing.returncode:
            call(['secrets','create',name,'--replication-policy=automatic','--project='+project])
            call(['secrets','versions','add',name,'--data-file=-','--project='+project],input_value=private[key])
        call(['secrets','add-iam-policy-binding',name,'--member=serviceAccount:'+runtime,'--role=roles/secretmanager.secretAccessor','--project='+project])
    print('Initialized dedicated runtime/build identities, versioned private storage, and Secret Manager values.',flush=True)

print('Building and deploying the course service; no credentials are included in source.',flush=True)
command=[args.gcloud,'run','deploy','mles-course','--source=.',
    '--project='+project,'--region='+region,'--service-account='+runtime,
    '--build-service-account=projects/'+project+'/serviceAccounts/'+builder,
    '--allow-unauthenticated','--cpu=1','--memory=512Mi','--min-instances=0',
    '--max-instances=3','--concurrency=40','--timeout=120',
    '--set-env-vars=APP_ENV=production,COURSE_BUCKET='+bucket,
    '--set-secrets=SESSION_SECRET=mles-session-key:latest,ADMIN_PASSWORD_HASH=mles-admin-password-hash:latest','--quiet']
subprocess.run(command,cwd=ROOT,check=True)
result=call(['run','services','describe','mles-course','--region='+region,'--project='+project,'--format=json'])
service=json.loads(result.stdout)
status=service.get('status',{})
record={'project':project,'region':region,'service':'mles-course','bucket':bucket,
    'url':status.get('url'),'latest_ready_revision':status.get('latestReadyRevisionName'),
    'traffic':status.get('traffic'),'persistence':'private versioned Cloud Storage bucket',
    'authentication':'password hashes + signed HttpOnly secure sessions; per-account role checks',
    'secrets':'Google Secret Manager; no password or secret value in this record'}
(ROOT/'deployment'/'deployment.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record,indent=2),flush=True)
