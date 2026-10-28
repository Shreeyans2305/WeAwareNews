from pathlib import Path
import shutil, tempfile, json, subprocess
from datetime import datetime, timezone
staging=Path(tempfile.mkdtemp(prefix='weaware-sherlock-build-'))
backend=Path('backend')
for name in ('api','research'):
 shutil.copytree(backend/name,staging/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.env*'))
for name in ('Dockerfile','requirements-api.txt'):
 shutil.copy2(backend/name,staging/name)
stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
repo='us-central1-docker.pkg.dev/weaware/cloud-run-source-deploy'
api=f'{repo}/weaware-api:sherlock-pilot-{stamp}'
worker=f'{repo}/weaware-sherlock-worker:pilot-{stamp}'
config={'steps':[{'name':'gcr.io/cloud-builders/docker','args':['build','-t',api,'.']},
                 {'name':'gcr.io/cloud-builders/docker','args':['build','-f','research/Dockerfile','-t',worker,'.']}],
        'images':[api,worker],'options':{'logging':'CLOUD_LOGGING_ONLY'},'timeout':'1200s'}
(staging/'cloudbuild.json').write_text(json.dumps(config))
p=subprocess.run(['gcloud','builds','submit',str(staging),'--project=weaware','--config='+str(staging/'cloudbuild.json'),'--async','--format=json','--quiet'],capture_output=True,text=True)
if p.returncode:
 print(p.stderr);raise SystemExit(p.returncode)
build=json.loads(p.stdout)
state={'buildId':build['id'],'staging':str(staging),'apiImage':api,'workerImage':worker}
Path('tmp/sherlock-deploy/build-state.json').write_text(json.dumps(state,indent=2))
print(json.dumps(state,indent=2))
