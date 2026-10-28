import subprocess, json, urllib.request, urllib.error
from pathlib import Path
for account in ['theactiverecord@gmail.com','weaware.news@gmail.com']:
 p=subprocess.run(['gcloud','auth','print-access-token','--account='+account],capture_output=True,text=True)
 if p.returncode:
  print(account,'credential unavailable');continue
 token=p.stdout.strip()
 for quota in ['weaware','weaware-3504c']:
  data={'email':['theactiverecord@gmail.com','weaware.news@gmail.com']}
  req=urllib.request.Request('https://identitytoolkit.googleapis.com/v1/projects/weaware-3504c/accounts:lookup',data=json.dumps(data).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','x-goog-user-project':quota})
  try:
   with urllib.request.urlopen(req,timeout=30) as r: response=json.load(r)
   users=[{k:u.get(k) for k in ('localId','email','emailVerified','disabled')} for u in response.get('users',[])]
   print(account,quota,'users',json.dumps(users))
   if users:
    Path('tmp/sherlock-deploy/testers.json').write_text(json.dumps(users,indent=2))
    Path('tmp/sherlock-deploy/firebase-access.json').write_text(json.dumps({'account':account,'quotaProject':quota,'project':'weaware-3504c'}))
    raise SystemExit(0)
  except urllib.error.HTTPError as e:
   error=json.load(e).get('error',{})
   print(account,quota,e.code,error.get('message'),[{k:d.get(k) for k in ('reason','metadata') if k in d} for d in error.get('details',[])])
