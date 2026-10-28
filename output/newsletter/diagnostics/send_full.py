import json,os,secrets,subprocess,base64,hmac,hashlib,smtplib,ssl,time
from pathlib import Path
from email.message import EmailMessage
from email.utils import make_msgid,formatdate
from backend.api.newsletter import render_newsletter
from backend.tests.test_newsletter_delivery import scope

def get_secret(name):
 return subprocess.check_output(['gcloud','secrets','versions','access','latest','--secret='+name,'--project=weaware'],text=True).strip()
password=get_secret('newsletter-smtp-password')
secret=get_secret('newsletter-unsubscribe-secret')
os.environ.update(NEWSLETTER_SMTP_USER='weaware.news@gmail.com',NEWSLETTER_FROM_EMAIL='WeAware <weaware.news@gmail.com>',NEWSLETTER_SMTP_PASSWORD=password)
uid=base64.urlsafe_b64encode(('oneoff-test-'+secrets.token_hex(16)).encode()).decode().rstrip('=')
token=uid+'.'+hmac.new(secret.encode(),uid.encode(),hashlib.sha256).hexdigest()
unsubscribe='https://weaware-api-nrebbbg6na-uc.a.run.app/api/v1/newsletters/unsubscribe?token='+token
articles=json.loads(Path('output/newsletter/articles.json').read_text())
body,text=render_newsletter(articles,'daily',unsubscribe,test=True)
Path('output/newsletter/crosscheck-preview.html').write_text(body)
# Same content, URLs, images, and MIME encoding; only the unsubscribe headers differ.
run=secrets.token_hex(3)
m=EmailMessage();m['From']='WeAware <weaware.news@gmail.com>';m['To']='shreeyans.vichare@gmail.com';m['Subject']=f'Crosscheck complete {run} E';m['Date']=formatdate(usegmt=True);m['Reply-To']='weaware.news@gmail.com';m['Message-ID']=make_msgid(domain='gmail.com');m.set_content(text);m.add_alternative(body,subtype='html')
with smtplib.SMTP_SSL('smtp.gmail.com',465,context=ssl.create_default_context(),timeout=30) as smtp:
 smtp.login('weaware.news@gmail.com',password.replace(' ',''));smtp.send_message(m)
time.sleep(3)
subject=f'The Crosscheck | Full illustrated edition {run}'
scope['_send_newsletter_email']('shreeyans.vichare@gmail.com',subject,body,text,unsubscribe,'weaware-final-'+secrets.token_hex(16))
results=dict(control_subject=str(m['Subject']),final_subject=subject,images=body.count('<img '),html_bytes=len(body.encode()))
Path('output/newsletter/diagnostics/full.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results))
