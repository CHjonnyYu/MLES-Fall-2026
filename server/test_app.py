"""Security and persistence checks using an isolated local store, never live data."""
import io,json,secrets,tempfile,unittest
from pathlib import Path
from werkzeug.security import generate_password_hash
from server.app import create_app


class CourseCMSChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=create_app({'TESTING':True,'SECRET_KEY':secrets.token_hex(32),
            'ADMIN_PASSWORD_HASH':generate_password_hash('test-password-only'),
            'SESSION_COOKIE_SECURE':False,'BUCKET':'','DATA_DIR':self.temp.name})
        self.client=self.app.test_client()

    def tearDown(self):self.temp.cleanup()

    def token(self,client=None):
        client=client or self.client
        client.get('/admin/login')
        with client.session_transaction() as state:return state['csrf']

    def login(self,username='admin',password='test-password-only',client=None):
        client=client or self.client
        result=client.post('/admin/login',data={'csrf':self.token(client),'username':username,'password':password})
        self.assertEqual(result.status_code,302)
        with client.session_transaction() as state:self.csrf=state['csrf']

    def revision(self):return self.app.extensions['course_store'].load()['revision']

    def test_access_and_csrf(self):
        self.assertEqual(self.client.get('/admin/').status_code,302)
        self.login()
        self.assertEqual(self.client.get('/admin/').status_code,200)
        self.assertEqual(self.client.post('/admin/weeks/07',data={'title':'bad'}).status_code,400)
        for path in ['/server/app.py','/.git/config','/.env','/Dockerfile']:
            self.assertEqual(self.client.get(path).status_code,404)
        public=self.client.get('/api/catalog').get_json()
        self.assertNotIn('password_hash',json.dumps(public))
        self.assertNotIn('session_secret',json.dumps(public))

    def test_draft_publish_and_edit(self):
        self.login()
        result=self.client.post('/admin/weeks/07/resources',data={'csrf':self.csrf,'revision':self.revision(),'title':'Attention companion','kind':'video','status':'draft','description':'Explain Q, K, V.','url':'https://www.3blue1brown.com/lessons/attention/'})
        self.assertEqual(result.status_code,302)
        anonymous=self.app.test_client()
        def resources():return next(w for w in anonymous.get('/api/catalog').get_json()['weeks'] if w['number']=='07')['resources']
        self.assertEqual(resources(),[])
        record=self.app.extensions['course_store'].load()['weeks']['07']['resources'][0]
        result=self.client.post('/admin/weeks/07/resources/'+record['id'],data={'csrf':self.csrf,'revision':self.revision(),'action':'published'})
        self.assertEqual(result.status_code,302)
        self.assertEqual(resources()[0]['title'],'Attention companion')

    def test_uploaded_notebook_and_draft_visibility(self):
        self.login()
        raw=json.dumps({'nbformat':4,'nbformat_minor':5,'metadata':{},'cells':[]}).encode()
        result=self.client.post('/admin/weeks/07/resources',data={'csrf':self.csrf,'revision':self.revision(),'title':'Extra notebook','kind':'notebook','status':'draft','description':'Self-contained file.','file':(io.BytesIO(raw),'extra.ipynb')})
        self.assertEqual(result.status_code,302)
        record=self.app.extensions['course_store'].load()['weeks']['07']['resources'][0]
        self.assertEqual(self.client.get(record['url']).status_code,200)
        anonymous=self.app.test_client()
        self.assertEqual(anonymous.get(record['url']).status_code,404)
        self.client.post('/admin/weeks/07/resources/'+record['id'],data={'csrf':self.csrf,'revision':self.revision(),'action':'published'})
        self.assertEqual(anonymous.get(record['url']).data,raw)

    def test_revisions_and_persistence(self):
        self.login();old=self.revision()
        form={'csrf':self.csrf,'revision':old,'title':'Updated sequence lesson','focus':'Learn state and retrieval.','date':'2026-10-19','phase':'Sequence models'}
        self.assertEqual(self.client.post('/admin/weeks/07',data=form).status_code,302)
        self.assertEqual(self.client.post('/admin/weeks/07',data=form).status_code,409)
        persisted=json.loads((Path(self.temp.name)/'catalog.json').read_text())
        self.assertEqual(persisted['weeks']['07']['title'],'Updated sequence lesson')
        self.assertNotIn('test-password-only',json.dumps(persisted))

    def test_ta_role_and_revocation(self):
        self.login()
        result=self.client.post('/admin/users',data={'csrf':self.csrf,'revision':self.revision(),'username':'ta01','password':'assistant-test','role':'ta','active':'yes'})
        self.assertEqual(result.status_code,302)
        ta=self.app.test_client();self.login('ta01','assistant-test',ta)
        ta_token=self.csrf
        self.assertEqual(ta.post('/admin/users',data={'csrf':ta_token}).status_code,403)
        with self.client.session_transaction() as state:admin_token=state['csrf']
        self.client.post('/admin/users',data={'csrf':admin_token,'revision':self.revision(),'username':'ta01','password':'','role':'ta'})
        self.assertEqual(ta.get('/admin/').status_code,302)

    def test_html_sandbox_and_blocked_urls(self):
        self.login()
        base={'csrf':self.csrf,'revision':self.revision(),'title':'Bad URL','kind':'video','status':'draft','description':''}
        result=self.client.post('/admin/weeks/07/resources',data={**base,'url':'javascript:alert(1)'})
        self.assertEqual(result.status_code,400)
        result=self.client.post('/admin/weeks/07/resources',data={**base,'title':'Slide example','kind':'slides','status':'published','file':(io.BytesIO(b'<h1>Teaching slide</h1>'),'slide.html')})
        self.assertEqual(result.status_code,302)
        record=self.app.extensions['course_store'].load()['weeks']['07']['resources'][0]
        response=self.client.get(record['url'])
        self.assertIn('sandbox',response.headers['Content-Security-Policy'])
        self.assertNotIn('allow-same-origin',response.headers['Content-Security-Policy'])

    def test_login_throttle(self):
        for _ in range(5):
            response=self.client.post('/admin/login',data={'csrf':self.token(),'username':'admin','password':'wrong'})
            self.assertEqual(response.status_code,401)
        response=self.client.post('/admin/login',data={'csrf':self.token(),'username':'admin','password':'wrong'})
        self.assertEqual(response.status_code,429)


if __name__=='__main__':unittest.main()
