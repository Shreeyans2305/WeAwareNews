import gzip, hashlib, json, subprocess, urllib.request, urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
access=json.loads(Path('tmp/sherlock-deploy/firebase-access.json').read_text())
token=subprocess.run(['gcloud','auth','print-access-token','--account='+access['account']],capture_output=True,text=True,check=True).stdout.strip()
headers={'Authorization':'Bearer '+token,'x-goog-user-project':access['quotaProject']}
root='https://firebasehosting.googleapis.com/v1beta1/'
def request(path,data=None,method=None):
 req=urllib.request.Request(root+path,data=json.dumps(data).encode() if data is not None else None,method=method,
                           headers={**headers,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=60) as r: return json.load(r)
 except urllib.error.HTTPError as e:
  error=json.load(e).get('error',{});raise RuntimeError(str(e.code)+' '+error.get('message','Hosting request failed'))
site='sites/weaware-3504c'
previous=request(site+'/releases?pageSize=1')
Path('tmp/sherlock-deploy/hosting-previous.json').write_text(json.dumps(previous))
# Only Vite's static output is uploaded; private .env/config files are excluded.
dist=Path('WEAWARE/dist')
files={}; blobs={}
for path in sorted(dist.rglob('*')):
 if not path.is_file() or any(part.startswith('.') for part in path.relative_to(dist).parts): continue
 body=gzip.compress(path.read_bytes(),compresslevel=6,mtime=0)
 digest=hashlib.sha256(body).hexdigest()
 files['/'+path.relative_to(dist).as_posix()]=digest
 blobs[digest]=body
# Protect against accidentally compiled unrelated mail credentials.
for line in Path('WEAWARE/.env.local').read_text().splitlines():
 if line.startswith('RESEND_API_KEY='):
  private=line.split('=',1)[1].strip().strip('"\'').encode()
  if private and any(private in p.read_bytes() for p in dist.rglob('*') if p.is_file()):
   raise RuntimeError('A private credential appeared in static output; deployment stopped')
version=request(site+'/versions',{'config':{'rewrites':[{'glob':'**','path':'/index.html'}],
 'headers':[{'glob':'/assets/**','headers':{'Cache-Control':'public,max-age=31536000,immutable'}},
            {'glob':'/index.html','headers':{'Cache-Control':'no-cache'}}]}})
name=version['name']
populated=request(name+':populateFiles',{'files':files})
upload=populated.get('uploadUrl','')
if not upload.startswith('https://upload-firebasehosting.googleapis.com/upload/sites/weaware-3504c/'):
 raise RuntimeError('Unexpected upload destination')
def send(digest):
 req=urllib.request.Request(upload+'/'+digest,data=blobs[digest],method='POST',headers={**headers,'Content-Type':'application/octet-stream'})
 with urllib.request.urlopen(req,timeout=120) as r: r.read()
 return digest
with ThreadPoolExecutor(max_workers=4) as pool:
 uploaded=list(pool.map(send,populated.get('uploadRequiredHashes',[])))
request(name+'?updateMask=status',{'status':'FINALIZED'},'PATCH')
release=request(site+'/releases?versionName='+name,{'message':'Sherlock Mode website-first pilot with private PDF reports'})
summary={'url':'https://weaware-3504c.web.app','version':name,'release':release.get('name'),
         'files':len(files),'uploadedFiles':len(uploaded)}
Path('tmp/sherlock-deploy/hosting-release.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
