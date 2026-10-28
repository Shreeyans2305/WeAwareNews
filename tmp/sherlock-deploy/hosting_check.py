import subprocess, urllib.request, urllib.error, json
from pathlib import Path
access=json.loads(Path('tmp/sherlock-deploy/firebase-access.json').read_text())
token=subprocess.run(['gcloud','auth','print-access-token','--account='+access['account']],capture_output=True,text=True,check=True).stdout.strip()
for label,url in [('hosting','https://firebasehosting.googleapis.com/v1beta1/projects/weaware-3504c/sites'),('domains','https://identitytoolkit.googleapis.com/admin/v2/projects/weaware-3504c/config')]:
 req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,'x-goog-user-project':'weaware-3504c'})
 try:
  with urllib.request.urlopen(req,timeout=30) as r: data=json.load(r)
  print(label, json.dumps(data if label=='hosting' else data.get('authorizedDomains',[])))
  if label=='hosting': Path('tmp/sherlock-deploy/hosting-sites.json').write_text(json.dumps(data))
 except urllib.error.HTTPError as e:
  error=json.load(e).get('error',{})
  print(label,e.code,error.get('message'))
