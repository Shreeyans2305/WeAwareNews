import subprocess, urllib.request, urllib.error, json
from pathlib import Path
from urllib.parse import urlencode

def sign_in(email):
 values={}
 for line in Path('WEAWARE/.env.local').read_text().splitlines():
  if line.startswith('VITE_FIREBASE_') and '=' in line:
   key,value=line.split('=',1);values[key]=value.strip().strip('"\'')
 token=subprocess.run(['gcloud','auth','print-access-token','--account='+email],capture_output=True,text=True,check=True).stdout.strip()
 body={'requestUri':'https://weaware-3504c.web.app','postBody':urlencode({'access_token':token,'providerId':'google.com'}),'returnSecureToken':True}
 request=urllib.request.Request('https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key='+values['VITE_FIREBASE_API_KEY'],
                                data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(request,timeout=45) as response: data=json.load(response)
 except urllib.error.HTTPError as error:
  message=json.load(error).get('error',{}).get('message','Sign-in failed')
  raise RuntimeError('Firebase sign-in failed: '+message.split(':')[0])
 return {'token':data['idToken'],'uid':data['localId'],'email':data.get('email'),'newUser':data.get('isNewUser',False)}

if __name__=='__main__':
 for email in ['theactiverecord@gmail.com','weaware.news@gmail.com']:
  try:
   result=sign_in(email)
   print(json.dumps({k:v for k,v in result.items() if k!='token'}))
  except Exception as exc: print(email,str(exc))
