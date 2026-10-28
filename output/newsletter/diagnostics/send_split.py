import re,json,smtplib,ssl,subprocess,secrets,time
from pathlib import Path
from email.message import EmailMessage
from email.utils import formatdate,make_msgid
body=Path('output/newsletter/crosscheck-preview.html').read_text()
no_links=re.sub(r'<a\b[^>]*>(.*?)</a>',r'\1',body,flags=re.S)
no_images=re.sub(r'<img\b[^>]*>','',body)
variants=[('G','all images, no links',no_links),('H','all links, no images',no_images)]
password=subprocess.check_output(['gcloud','secrets','versions','access','latest','--secret=newsletter-smtp-password','--project=weaware'],text=True).strip().replace(' ','')
run=secrets.token_hex(3);sent=[]
with smtplib.SMTP_SSL('smtp.gmail.com',465,context=ssl.create_default_context(),timeout=30) as smtp:
 smtp.login('weaware.news@gmail.com',password)
 for code,description,html in variants:
  m=EmailMessage();m['From']='WeAware <weaware.news@gmail.com>';m['To']='shreeyans.vichare@gmail.com';m['Subject']=f'Crosscheck isolation {run} {code}';m['Date']=formatdate(usegmt=True);m['Reply-To']='weaware.news@gmail.com';m['Message-ID']=make_msgid(domain='gmail.com')
  # Same minimal plain alternative in both variants, so HTML is the only difference.
  m.set_content('Your requested one-time Crosscheck placement comparison. The newsletter is included as HTML. No recurring subscription was created.');m.add_alternative(html,subtype='html');smtp.send_message(m)
  sent.append(dict(subject=str(m['Subject']),description=description));time.sleep(3)
Path('output/newsletter/diagnostics/split.json').write_text(json.dumps(sent,indent=2));print(json.dumps(sent))
