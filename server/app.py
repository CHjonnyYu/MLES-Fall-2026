"""Course portal + authenticated TA CMS, persistent on Google Cloud Storage."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from functools import wraps
from pathlib import Path
import copy, fcntl, hashlib, json, mimetypes, os, re, secrets, time, uuid
from urllib.parse import urljoin, urlsplit

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_file, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix

ROOT = Path(__file__).resolve().parents[1]
KINDS = {'slides', 'notebook', 'video', 'github', 'reading'}
ALLOWED = {'.pdf', '.ipynb', '.html', '.pptx', '.png', '.jpg', '.jpeg', '.csv', '.tex'}
MIMES = {'.ipynb':'application/json', '.html':'text/html; charset=utf-8', '.pdf':'application/pdf', '.tex':'text/plain; charset=utf-8'}


class RevisionConflict(Exception):
    pass


class LocalStore:
    def __init__(self, directory, initial):
        self.root=Path(directory);self.root.mkdir(parents=True,exist_ok=True)
        self.catalog=self.root/'catalog.json';self.lock=self.root/'catalog.lock';self.initial=initial

    @contextmanager
    def locked(self):
        with self.lock.open('a') as handle:
            fcntl.flock(handle,fcntl.LOCK_EX)
            try:yield
            finally:fcntl.flock(handle,fcntl.LOCK_UN)

    def load(self):
        with self.locked():
            return json.loads(self.catalog.read_text()) if self.catalog.exists() else self.initial()

    def mutate(self, change, expected=None, bump=True):
        with self.locked():
            data=json.loads(self.catalog.read_text()) if self.catalog.exists() else self.initial()
            if expected is not None and data['revision']!=expected:raise RevisionConflict()
            result=change(data)
            if bump:data['revision']+=1
            temporary=self.catalog.with_suffix('.new')
            temporary.write_text(json.dumps(data,ensure_ascii=False));temporary.chmod(0o600)
            os.replace(temporary,self.catalog)
            return result

    def put(self,key,content,content_type):
        target=self.root/key;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(content)

    def get(self,key):return (self.root/key).read_bytes()


class CloudStore:
    def __init__(self,bucket,initial):
        from google.cloud import storage
        self.bucket=storage.Client().bucket(bucket);self.initial=initial

    def snapshot(self):
        from google.api_core.exceptions import NotFound, PreconditionFailed
        for _ in range(5):
            blob=self.bucket.blob('cms/catalog.json')
            try:
                blob.reload()
                generation=int(blob.generation)
                return json.loads(blob.download_as_bytes(if_generation_match=generation)),generation
            except NotFound:return self.initial(),0
            except PreconditionFailed:continue
        raise RevisionConflict()

    def load(self):return self.snapshot()[0]

    def mutate(self,change,expected=None,bump=True):
        from google.api_core.exceptions import PreconditionFailed
        for _ in range(5):
            data,generation=self.snapshot()
            if expected is not None and data['revision']!=expected:raise RevisionConflict()
            result=change(data)
            if bump:data['revision']+=1
            try:
                self.bucket.blob('cms/catalog.json').upload_from_string(json.dumps(data,ensure_ascii=False),content_type='application/json',if_generation_match=generation)
                return result
            except PreconditionFailed:continue
        raise RevisionConflict()

    def put(self,key,content,content_type):
        self.bucket.blob(key).upload_from_string(content,content_type=content_type,if_generation_match=0)

    def get(self,key):return self.bucket.blob(key).download_as_bytes()


def create_app(overrides=None):
    app=Flask(__name__,template_folder='templates')
    environment=os.environ.get('APP_ENV','production')
    private_config=Path.home()/'.config'/'mles-course'/'local-secrets.json'
    local={}
    if environment=='development' and private_config.exists():local=json.loads(private_config.read_text())
    app.config.update(SECRET_KEY=os.environ.get('SESSION_SECRET') or local.get('session_secret'),
        ADMIN_PASSWORD_HASH=os.environ.get('ADMIN_PASSWORD_HASH') or local.get('admin_password_hash'),
        SESSION_COOKIE_NAME='mles_session',SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=environment!='development',SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=4),MAX_CONTENT_LENGTH=52*1024*1024,
        BUCKET=os.environ.get('COURSE_BUCKET',''),GITHUB_REPOSITORY='CHjonnyYu/MLES-Fall-2026')
    if overrides:app.config.update(overrides)
    if not app.config['SECRET_KEY'] or not app.config['ADMIN_PASSWORD_HASH']:
        raise RuntimeError('Configure SESSION_SECRET and ADMIN_PASSWORD_HASH before starting the course CMS.')
    if environment=='production' and not app.config['BUCKET'] and not app.config.get('TESTING'):
        raise RuntimeError('Production requires COURSE_BUCKET for persistent state.')
    app.wsgi_app=ProxyFix(app.wsgi_app,x_for=1,x_proto=1)

    def initial():
        manifest=json.loads((ROOT/'course.json').read_text())
        return {'revision':1,'weeks':{w['number']:{**w,'resources':[]} for w in manifest['weeks']},
            'users':{'admin':{'password_hash':app.config['ADMIN_PASSWORD_HASH'],'role':'admin','active':True,'auth_version':1}},
            'audit':[],'login_failures':{}}

    store=CloudStore(app.config['BUCKET'],initial) if app.config['BUCKET'] else LocalStore(app.config.get('DATA_DIR',str(Path.home()/'.config'/'mles-course'/'data')),initial)
    app.extensions['course_store']=store

    def audit(data,action,target,actor=None):
        data['audit'].append({'time':datetime.now(timezone.utc).isoformat(),'actor':actor or session.get('user','anonymous'),'action':action,'target':str(target)})
        data['audit']=data['audit'][-500:]

    def current_user():
        username=session.get('user')
        if not username:return None
        user=store.load()['users'].get(username)
        if not user or not user.get('active') or user['auth_version']!=session.get('auth_version'):
            session.clear();return None
        return {'username':username,'role':user['role']}

    def protected(admin=False):
        def decorator(function):
            @wraps(function)
            def wrapped(*args,**kwargs):
                user=current_user()
                if not user:return redirect(url_for('login'))
                if admin and user['role']!='admin':abort(403)
                return function(*args,**kwargs)
            return wrapped
        return decorator

    def revision():
        try:return int(request.form['revision'])
        except (KeyError,ValueError):abort(400,'Missing content revision. Reload the editor.')

    def valid_url(value,optional=False):
        value=value.strip()
        if not value and optional:return ''
        parts=urlsplit(value)
        if parts.scheme=='https' and parts.netloc and not parts.username and not parts.password:return value
        if value.startswith('/') and not value.startswith('//') and not parts.scheme and '\\' not in value:return value
        abort(400,'Use an HTTPS URL or a course-relative path beginning with /.')

    @app.before_request
    def csrf_guard():
        if request.path.startswith('/admin'):
            session.setdefault('csrf',secrets.token_urlsafe(32))
            if request.method=='POST':
                token=request.form.get('csrf','')
                if not token or not secrets.compare_digest(token,session['csrf']):abort(400,'Invalid form token. Reload the page.')

    @app.after_request
    def response_headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='same-origin'
        if request.path.startswith('/admin'):
            response.headers['Cache-Control']='no-store'
            response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'none'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
        return response

    @app.errorhandler(RevisionConflict)
    def conflict(_):return render_template('error.html',message='Another editor changed the course. Reload the week and apply your changes again.'),409

    @app.errorhandler(413)
    def too_large(_):return render_template('error.html',message='File too large. Use a file below 50 MB; add videos as external links.'),413

    @app.get('/healthz')
    def health():
        store.load()
        return jsonify(status='ok',persistence='cloud-storage' if app.config['BUCKET'] else 'local-file')

    @app.route('/admin/login',methods=['GET','POST'])
    def login():
        if request.method=='GET':return render_template('login.html')
        username=request.form.get('username','').strip().lower()[:80]
        password=request.form.get('password','')
        identity=hashlib.sha256((request.remote_addr+'|'+username).encode()).hexdigest()
        now=time.time();data=store.load()
        attempts=[t for t in data['login_failures'].get(identity,[]) if now-t<900]
        if len(attempts)>=5:return render_template('login.html',error='Too many attempts. Try again after 15 minutes.'),429
        user=data['users'].get(username)
        candidate=user['password_hash'] if user else app.config['ADMIN_PASSWORD_HASH']
        matched=check_password_hash(candidate,password)
        if not user or not user.get('active') or not matched:
            def failed(state):
                state['login_failures']={k:[t for t in v if now-t<900] for k,v in state['login_failures'].items() if any(now-t<900 for t in v)}
                state['login_failures'].setdefault(identity,[]).append(now)
            store.mutate(failed,bump=False)
            return render_template('login.html',error='Incorrect username or password.'),401
        session.clear();session.update(user=username,auth_version=user['auth_version'],csrf=secrets.token_urlsafe(32));session.permanent=True
        def logged_in(state):
            state['login_failures'].pop(identity,None);audit(state,'login',username)
        store.mutate(logged_in,bump=False)
        return redirect(url_for('dashboard'))

    @app.post('/admin/logout')
    def logout():
        session.clear();return redirect(url_for('login'))

    @app.get('/admin')
    @app.get('/admin/')
    @protected()
    def dashboard():
        data=store.load();number=request.args.get('week','07')
        if number not in data['weeks']:abort(404)
        return render_template('dashboard.html',data=data,selected=data['weeks'][number],user=current_user(),kinds=sorted(KINDS))

    @app.post('/admin/weeks/<number>')
    @protected()
    def edit_week(number):
        title=request.form.get('title','').strip();focus=request.form.get('focus','').strip()
        date=request.form.get('date','').strip();phase=request.form.get('phase','').strip()
        if not 1<=len(title)<=180 or len(focus)>2500:abort(400,'Provide a title under 180 characters and focus under 2500 characters.')
        try:
            if datetime.strptime(date,'%Y-%m-%d').weekday()!=0:abort(400,'Course dates must be Mondays.')
        except ValueError:abort(400,'Use a valid date.')
        def update(data):
            if number not in data['weeks']:abort(404)
            data['weeks'][number].update(title=title,focus=focus,date=date,phase=phase[:40]);audit(data,'update week',number)
        store.mutate(update,revision());flash('Weekly progress updated.');return redirect(url_for('dashboard',week=number))

    @app.post('/admin/weeks/<number>/resources')
    @protected()
    def add_resource(number):
        title=request.form.get('title','').strip();kind=request.form.get('kind','')
        description=request.form.get('description','').strip()
        status=request.form.get('status','draft')
        if not 1<=len(title)<=180 or kind not in KINDS or status not in ['draft','published'] or len(description)>3000:abort(400,'Check title, type, status, and description.')
        identifier=uuid.uuid4().hex
        resource={'id':identifier,'title':title,'kind':kind,'description':description,'status':status,'created_at':datetime.now(timezone.utc).isoformat()}
        uploaded=request.files.get('file')
        if uploaded and uploaded.filename:
            filename=secure_filename(uploaded.filename);suffix=Path(filename).suffix.lower()
            if not filename or suffix not in ALLOWED:abort(400,'Unsupported file extension.')
            content=uploaded.read(50*1024*1024+1)
            if len(content)>50*1024*1024:abort(413)
            if suffix=='.ipynb':
                try:
                    notebook=json.loads(content)
                    if notebook.get('nbformat')!=4 or not isinstance(notebook.get('cells'),list) or len(notebook['cells'])>5000:raise ValueError()
                except (ValueError,UnicodeError):abort(400,'Upload a valid version-4 Jupyter notebook.')
            key=f'uploads/{identifier}/{filename}'
            store.put(key,content,MIMES.get(suffix,mimetypes.guess_type(filename)[0] or 'application/octet-stream'))
            resource.update(url=f'/materials/{identifier}/{filename}',object_key=key,filename=filename,sha256=hashlib.sha256(content).hexdigest())
        else:resource['url']=valid_url(request.form.get('url',''))
        colab=valid_url(request.form.get('colab_url',''),optional=True)
        if colab:
            if urlsplit(colab).hostname!='colab.research.google.com':abort(400,'Colab URL must use colab.research.google.com.')
            resource['colab_url']=colab
        elif kind=='notebook' and urlsplit(resource['url']).hostname=='github.com':
            resource['colab_url']=resource['url'].replace('https://github.com/','https://colab.research.google.com/github/',1)
        def add(data):
            if number not in data['weeks']:abort(404)
            data['weeks'][number]['resources'].append(resource);audit(data,'add '+status+' resource',identifier)
        store.mutate(add,revision());flash('Resource saved. Published resources appear on the student site.');return redirect(url_for('dashboard',week=number))

    @app.post('/admin/weeks/<number>/resources/<identifier>')
    @protected()
    def edit_resource(number,identifier):
        action=request.form.get('action')
        def update(data):
            if number not in data['weeks']:abort(404)
            resources=data['weeks'][number]['resources']
            item=next((r for r in resources if r['id']==identifier),None)
            if not item:abort(404)
            if action=='remove':resources.remove(item)
            elif action in ['draft','published']:item['status']=action
            elif action=='edit':
                title=request.form.get('title','').strip();description=request.form.get('description','').strip()
                if not 1<=len(title)<=180 or len(description)>3000:abort(400)
                item.update(title=title,description=description)
                if not item.get('object_key'):item['url']=valid_url(request.form.get('url',''))
                colab=valid_url(request.form.get('colab_url',''),optional=True)
                if colab and urlsplit(colab).hostname!='colab.research.google.com':abort(400)
                item['colab_url']=colab
            else:abort(400)
            audit(data,action+' resource',identifier)
        store.mutate(update,revision());flash('Resource updated.');return redirect(url_for('dashboard',week=number))

    @app.post('/admin/users')
    @protected(admin=True)
    def manage_user():
        username=request.form.get('username','').strip().lower();password=request.form.get('password','')
        role=request.form.get('role','ta');active=request.form.get('active')=='yes'
        if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{2,39}',username) or role not in ['ta','admin']:abort(400,'Use a 3–40 character username and a valid role.')
        if password and len(password)<5:abort(400,'Use at least 5 characters.')
        def update(data):
            old=data['users'].get(username)
            if not old and not password:abort(400,'A new user needs a password.')
            if username==session['user'] and (not active or role!='admin'):abort(400,'You cannot remove your own administrator access.')
            if old:
                old.update(active=active,role=role)
                if password:old['password_hash']=generate_password_hash(password)
                old['auth_version']+=1
            else:data['users'][username]={'password_hash':generate_password_hash(password),'role':role,'active':active,'auth_version':1}
            audit(data,'update account',username)
        store.mutate(update,revision(),bump=False)
        flash('Account saved. Password or role changes invalidate existing sessions.');return redirect(url_for('dashboard'))

    @app.get('/api/catalog')
    def public_catalog():
        data=store.load()
        weeks=[]
        for week in data['weeks'].values():
            public={k:v for k,v in week.items() if k!='resources'}
            public['resources']=[{k:v for k,v in r.items() if k not in ['object_key','created_at','sha256']} for r in week['resources'] if r['status']=='published']
            weeks.append(public)
        response=jsonify(revision=data['revision'],weeks=weeks)
        response.headers['Cache-Control']='no-store'
        return response

    @app.get('/materials/<identifier>/<filename>')
    def material_file(identifier,filename):
        data=store.load()
        item=next((r for w in data['weeks'].values() for r in w['resources'] if r['id']==identifier and r.get('filename')==filename),None)
        if not item or (item['status']!='published' and not current_user()):abort(404)
        import io
        suffix=Path(filename).suffix.lower()
        response=send_file(io.BytesIO(store.get(item['object_key'])),mimetype=MIMES.get(suffix),download_name=filename,as_attachment=suffix not in ['.html','.pdf','.png','.jpg','.jpeg'])
        if suffix=='.html':response.headers['Content-Security-Policy']="sandbox allow-scripts allow-downloads; connect-src 'none'; form-action 'none'"
        response.headers['Cache-Control']='private,no-store' if item['status']=='draft' else 'public,max-age=60'
        return response

    def machine_learning_page():
        # Keep one authoritative ML page while supporting the course-hub URL.
        html=(ROOT/'index.html').read_text(encoding='utf-8')
        def absolute_resource(match):
            value=match.group('value')
            if not value or value.startswith(('/', '#')) or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',value):
                return match.group(0)
            return match.group('attribute')+'='+match.group('quote')+urljoin('/',value)+match.group('quote')
        html=re.sub(r'''(?P<attribute>\b(?:href|src))=(?P<quote>["'])(?P<value>[^"']*)(?P=quote)''',absolute_resource,html)
        return re.sub(r'(<nav\b[^>]*>)',r'\1<a href="/">All courses</a>',html,count=1)

    @app.get('/')
    def home():return send_from_directory(ROOT,'portal.html')

    @app.get('/index.html')
    def legacy_machine_learning():return machine_learning_page()

    @app.get('/courses/<slug>/')
    @app.get('/courses/<slug>/index.html')
    def course_home(slug):
        if slug=='machine-learning':return machine_learning_page()
        if slug not in {'digital-twin-ic-packaging','python-programming','optimization-reinforcement-learning'}:
            abort(404)
        return send_from_directory(ROOT/'courses'/slug,'index.html')

    @app.get('/<path:filename>')
    def public_static(filename):
        allowed_prefixes=['assets/','lectures/','notebooks/','notes/','slides/','textbook/','validation/']
        if filename in ['course.json','lecture-manifest.json','week-07-class-pack.zip'] or any(filename.startswith(p) for p in allowed_prefixes):
            if filename.endswith('/'):filename+='index.html'
            return send_from_directory(ROOT,filename)
        abort(404)

    return app


if __name__=='__main__':
    create_app().run(host='127.0.0.1',port=int(os.environ.get('PORT','8766')))
