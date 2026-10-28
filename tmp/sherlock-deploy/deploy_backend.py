import json,subprocess
from pathlib import Path

def run(args):
 r=subprocess.run(['gcloud']+args+['--project=weaware','--quiet'],capture_output=True,text=True)
 if r.returncode: raise RuntimeError(r.stderr)
 return r.stdout
state=json.loads(Path('tmp/sherlock-deploy/build-state.json').read_text())
worker='weaware-sherlock-worker@weaware.iam.gserviceaccount.com'
run(['secrets','add-iam-policy-binding','db-password','--member=serviceAccount:'+worker,'--role=roles/secretmanager.secretAccessor','--format=value(etag)'])
service=json.loads(run(['run','services','describe','weaware-api','--region=us-central1','--format=json']))
origins=next((e['value'] for e in service['spec']['template']['spec']['containers'][0]['env'] if e['name']=='WEAWARE_ALLOWED_ORIGINS'),'')
origins=','.join(dict.fromkeys(origins.split(',')+['https://weaware-3504c.web.app','https://weaware-3504c.firebaseapp.com','http://127.0.0.1:5180','http://localhost:5180']))
print(run(['run','services','update','weaware-api','--region=us-central1','--image='+state['apiImage'],'--update-env-vars=^|^SHERLOCK_ENABLED=true|WEAWARE_ALLOWED_ORIGINS='+origins,'--format=value(status.latestReadyRevisionName)']),flush=True)
env={'GOOGLE_CLOUD_PROJECT':'weaware','DB_HOST':'/cloudsql/weaware:us-central1:weaware-pg','DB_NAME':'weaware','DB_USER':'weaware_user','SHERLOCK_SEARCH_PROVIDER':'google','SHERLOCK_MODEL':'gemini-2.5-flash','SHERLOCK_INPUT_USD_PER_MILLION':'0.30','SHERLOCK_OUTPUT_USD_PER_MILLION':'2.50','SHERLOCK_SEARCH_USD_PER_CALL':'0.035','SHERLOCK_PAID_CALLS_ENABLED':'true','SHERLOCK_RATES_VERIFIED':'true'}
print(run(['run','jobs','deploy','weaware-sherlock-worker','--region=us-central1','--image='+state['workerImage'],'--service-account='+worker,'--tasks=1','--parallelism=1','--max-retries=0','--cpu=1','--memory=512Mi','--task-timeout=1500s','--set-cloudsql-instances=weaware:us-central1:weaware-pg','--set-secrets=DB_PASS=db-password:latest','--set-env-vars='+','.join(k+'='+v for k,v in env.items()),'--format=value(metadata.name)']),flush=True)
