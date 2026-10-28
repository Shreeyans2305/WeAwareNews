import json, subprocess, urllib.request, urllib.error
from pathlib import Path

def cloud_json(args):
 p=subprocess.run(['gcloud',*args,'--format=json'],capture_output=True,text=True)
 if p.returncode: raise RuntimeError('Cloud inspection failed: '+str(p.returncode))
 return json.loads(p.stdout)
service=cloud_json(['run','services','describe','weaware-api','--project=weaware','--region=us-central1'])
container=service['spec']['template']['spec']['containers'][0]
keys={'INSTANCE_CONNECTION_NAME','DB_USER','DB_NAME','GOOGLE_CLOUD_PROJECT','FIREBASE_PROJECT_ID','WEAWARE_ALLOWED_ORIGINS'}
safe={'revision': service['status']['latestReadyRevisionName'],'image':container['image'],
      'serviceAccount':service['spec']['template']['spec'].get('serviceAccountName'),
      'url':service['status']['url'],'config':{e['name']:e.get('value') for e in container.get('env',[]) if e['name'] in keys},
      'envNames':[e['name'] for e in container.get('env',[])],
      'secretNames':[e.get('valueFrom',{}).get('secretKeyRef',{}).get('name') for e in container.get('env',[]) if e.get('valueFrom')]}
Path('tmp/sherlock-deploy/deployment-state.json').write_text(json.dumps(safe,indent=2))
print(json.dumps(safe,indent=2))
token=subprocess.run(['gcloud','auth','print-access-token'],capture_output=True,text=True,check=True).stdout.strip()
def request(url,data=None):
 req=urllib.request.Request(url, data=json.dumps(data).encode() if data else None, headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','x-goog-user-project':'weaware-3504c'})
 try:
  with urllib.request.urlopen(req, timeout=30) as response: return json.load(response)
 except urllib.error.HTTPError as exc: return {'errorStatus':exc.code}
users=request('https://identitytoolkit.googleapis.com/v1/projects/weaware-3504c/accounts:lookup',{'email':['theactiverecord@gmail.com','weaware.news@gmail.com']})
testers=[{k:u.get(k) for k in ('localId','email','emailVerified','disabled')} for u in users.get('users',[])]
Path('tmp/sherlock-deploy/testers.json').write_text(json.dumps(testers,indent=2))
print('Tester lookup:',json.dumps(testers) if testers else json.dumps(users))
print('Hosting sites:',json.dumps(request('https://firebasehosting.googleapis.com/v1beta1/projects/weaware-3504c/sites')))
config=request('https://identitytoolkit.googleapis.com/admin/v2/projects/weaware-3504c/config')
print('Authorized website domains:',config.get('authorizedDomains',config.get('errorStatus')))
