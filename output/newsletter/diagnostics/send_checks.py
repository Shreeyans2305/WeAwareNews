"""One-off, explicitly requested placement comparisons; never changes subscriptions."""
import json,re,ssl,smtplib,subprocess,secrets,time
from pathlib import Path
from email.message import EmailMessage
from email.utils import formatdate,make_msgid
from backend.api.newsletter import render_newsletter

root=Path('output/newsletter/diagnostics')
articles=json.loads(Path('output/newsletter/articles.json').read_text())
body,text=render_newsletter(articles,'daily','https://weaware-api-nrebbbg6na-uc.a.run.app/api/v1/newsletters/unsubscribe?token=diagnostic-not-a-subscription',test=True)
# Strip unsubscribe for diagnostics and add it only in the explicit unsubscribe-URL check.
base=re.sub(r'<a href="[^"]+"[^>]*>Unsubscribe from email briefings</a>','One-time requested diagnostic; reply to contact WeAware.',body)
text=text[:text.rfind('Unsubscribe:')]
no_images=re.sub(r'<img\b[^>]*>','',base)
no_links=re.sub(r'<a\b[^>]*>(.*?)</a>',r'\1',no_images,flags=re.S)
no_urls_text=re.sub(r'https?://\S+','[source URL omitted for this diagnostic]',text)
image_match=re.search(r'<img\b[^>]*>',base)
variants={
 'A':('newspaper, no external URLs',no_links,no_urls_text),
 'B':('source links only',no_images,text),
 'C':('lead image only',no_links.replace('</h1>','</h1>'+image_match.group(0),1) if image_match else no_links,no_urls_text),
 'D':('unsubscribe URL only',no_links.replace('</body>','<p><a href="https://weaware-api-nrebbbg6na-uc.a.run.app/api/v1/newsletters/unsubscribe?token=diagnostic-not-a-subscription">Diagnostic unsubscribe endpoint URL</a></p></body>'),no_urls_text),
}
password=subprocess.check_output(['gcloud','secrets','versions','access','latest','--secret=newsletter-smtp-password','--project=weaware'],text=True).strip().replace(' ','')
run=secrets.token_hex(3);sent=[]
with smtplib.SMTP_SSL('smtp.gmail.com',465,context=ssl.create_default_context(),timeout=30) as smtp:
 smtp.login('weaware.news@gmail.com',password)
 for code,(description,html,plain) in variants.items():
  m=EmailMessage();m['From']='WeAware <weaware.news@gmail.com>';m['To']='shreeyans.vichare@gmail.com';m['Subject']=f'Crosscheck placement {run} {code}';m['Date']=formatdate(usegmt=True);m['Reply-To']='weaware.news@gmail.com';m['Message-ID']=make_msgid(domain='gmail.com')
  m.set_content(plain);m.add_alternative(html,subtype='html')
  smtp.send_message(m)
  sent.append(dict(code=code,description=description,subject=str(m['Subject']),message_id=str(m['Message-ID'])))
  time.sleep(2)
(root/'checks.json').write_text(json.dumps(sent,indent=2))
print(json.dumps(sent,indent=2))
