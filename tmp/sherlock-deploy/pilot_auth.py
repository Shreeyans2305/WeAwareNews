import json,base64,time,subprocess,urllib.request
from pathlib import Path

def api(url,body,headers=None):
 request=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json',**(headers or {})})
 with urllib.request.urlopen(request,timeout=45) as response:return json.load(response)
def sign_in(uid,email):
 sa='firebase-adminsdk-fbsvc@weaware-3504c.iam.gserviceaccount.com'
 token=subprocess.run(['gcloud','auth','print-access-token','--account=weaware.news@gmail.com'],capture_output=True,text=True,check=True).stdout.strip()
 def enc(value):return base64.urlsafe_b64encode(json.dumps(value,separators=(',',':')).encode()).decode().rstrip('=')
 now=int(time.time())
 payload=enc({'alg':'RS256','typ':'JWT'})+'.'+enc({'iss':sa,'sub':sa,'aud':'https://identitytoolkit.googleapis.com/google.identity.identitytoolkit.v1.IdentityToolkit','iat':now,'exp':now+3600,'uid':uid,'claims':{'email':email,'email_verified':True}})
 signed=api('https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/'+sa+':signBlob',{'payload':base64.b64encode(payload.encode()).decode()},{'Authorization':'Bearer '+token,'x-goog-user-project':'weaware-3504c'})
 custom=payload+'.'+base64.urlsafe_b64encode(base64.b64decode(signed['signedBlob'])).decode().rstrip('=')
 key=next(line.split('=',1)[1].strip().strip('\"\'') for line in Path('WEAWARE/.env.local').read_text().splitlines() if line.startswith('VITE_FIREBASE_API_KEY='))
 data=api('https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key='+key,{'token':custom,'returnSecureToken':True})
 return data['idToken']
if __name__=='__main__':
 sign_in('mWps5LpCO4hWPxuereYUeqO4V1l2','theactiverecord@gmail.com')
 print('Administrative pilot test session established. No tokens persisted.')
