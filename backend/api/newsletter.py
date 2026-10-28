"""Email-safe Crosscheck newspaper layout shared by dispatch and test messages."""
import json
from pathlib import Path
from datetime import datetime
from html import escape
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


IMAGE_REPLACEMENTS = json.loads(Path(__file__).with_name("newsletter_images.json").read_text())

def newsletter_subject(cadence, *, now=None):
    if cadence not in ('daily', 'weekly'):
        raise ValueError('Newsletter frequency must be daily or weekly')
    now = now or datetime.now(ZoneInfo('Asia/Kolkata'))
    if now.tzinfo is not None:
        now = now.astimezone(ZoneInfo('Asia/Kolkata'))
    day = now.day
    suffix = 'th' if 11 <= day % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
    return f'The Crosscheck {day}{suffix} {now:%B %Y} | {cadence.title()} Newsletter'


def safe_url(value):
    value = str(value or '')
    parsed = urlparse(value)
    return value if parsed.scheme in ('http', 'https') and parsed.hostname else None


def render_newsletter(articles, cadence, unsubscribe_url, *, test=False, now=None):
    """Return matching HTML/text. No scripts, trackers, web fonts, or hidden content."""
    now = now or datetime.now(ZoneInfo('Asia/Kolkata'))
    date = now.strftime('%B %d, %Y').replace(' 0', ' ')
    edition = 'Weekly edition' if cadence == 'weekly' else 'Daily edition'
    note = ('You requested this one-time preview. No recurring subscription was created.' if test
            else f'You subscribed to this {cadence} briefing with your selected topics.')
    e = lambda value: escape(str(value or ''), quote=True)
    cards, plain = [], ['THE CROSSCHECK', 'WeAware · ' + edition + ' · ' + date,
                        'The feed, distilled. Disagreement kept in.', '']
    for index, article in enumerate(articles[:8]):
        sources = [s for s in (article.get('sources') or []) if isinstance(s, dict)]
        title, summary = article.get('title', ''), article.get('summary', '')
        topic = article.get('topic') or 'World'
        score, minutes = article.get('consensus', 0), article.get('readMins', 1)
        source_links = []
        source_text = []
        for source in sources[:3]:
            url = safe_url(source.get('url'))
            if not url:
                continue
            label = source.get('outlet') or source.get('name') or urlparse(url).hostname
            stance = source.get('stance')
            suffix = f' · {e(stance)}' if stance else ''
            source_links.append(f'<a href="{e(url)}" style="color:#353735;text-decoration:underline">{e(label)}</a>{suffix}')
            source_text.append(f'{label}' + (f' ({stance})' if stance else ''))
        original_image = article.get('image')
        replacement = IMAGE_REPLACEMENTS.get(original_image or '', {})
        image = safe_url(replacement.get('url') or original_image)
        image_credit = replacement.get('credit')
        photo = (f'<img src="{e(image)}" alt="{e(title)}" width="632" style="display:block;width:100%;height:auto;border:0;margin:18px 0" />'
                 if image else '')
        if photo and image_credit:
            photo += f'<p style="font:11px/1.5 Arial,sans-serif;color:#585b59">Image: {e(image_credit)}</p>'
        paragraphs = [p for p in (article.get('body') or []) if isinstance(p, str)][:2] if index == 0 else []
        body = ''.join(f'<p style="margin:12px 0;font:16px/1.7 Georgia,serif">{e(p)}</p>' for p in paragraphs)
        flags = article.get('flaggedClaims') or []
        flag = flags[0] if flags else None
        flag_text = (flag.get('claim') or flag.get('text') or '') if isinstance(flag, dict) else str(flag or '')
        reason = (flag.get('reason') or flag.get('note') or '') if isinstance(flag, dict) else ''
        flag_html = (f'<div style="border-left:3px solid #17191b;padding:8px 14px;margin:18px 0"><p style="font:11px Arial,sans-serif;letter-spacing:2px;text-transform:uppercase">Worth a closer look</p><p style="font:italic 17px/1.5 Georgia,serif">{e(flag_text)}</p><p style="font:13px/1.6 Arial,sans-serif">{e(reason)}</p></div>' if flag_text else '')
        kicker = ('Top story · ' if index == 0 else '') + topic
        size = '34' if index == 0 else '25'
        cards.append(f'''<tr><td style="padding:26px 24px;border-bottom:1px solid #bab9b2">
<p style="margin:0 0 10px;font:11px Arial,sans-serif;letter-spacing:2px;text-transform:uppercase">{e(kicker)}</p>
<h2 style="margin:0;font:bold {size}px/1.12 Georgia,'Times New Roman',serif;letter-spacing:-.6px">{e(title)}</h2>
<p style="font:11px/1.6 Arial,sans-serif;color:#585b59">By WeAware Agents · {e(minutes)} min read · {len(sources)} sources</p>
{photo}<p style="font:17px/1.6 Georgia,serif;color:#454844">{e(summary)}</p>{body}
<p style="font:12px Arial,sans-serif"><span style="display:inline-block;border:1px solid #17191b;padding:7px 10px;font-weight:bold">{e(score)}% consensus</span></p>
{flag_html}<p style="font:12px/1.8 Arial,sans-serif;color:#585b59">Sources: {' &nbsp; / &nbsp; '.join(source_links) if source_links else 'Source details unavailable'}</p>
</td></tr>''')
        plain += [kicker.upper(), title, f'{score}% consensus · {minutes} min read · {len(sources)} sources', summary]
        plain += paragraphs
        if flag_text:
            plain += ['Worth a closer look: ' + flag_text, reason]
        plain += source_text + ['']
    unsub = safe_url(unsubscribe_url)
    if not unsub:
        raise ValueError('A valid unsubscribe URL is required')
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>The Crosscheck</title></head>
<body style="margin:0;padding:0;background:#eae9e3;color:#17191b">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eae9e3"><tr><td align="center" style="padding:24px 8px">
<table role="presentation" width="680" cellpadding="0" cellspacing="0" style="width:100%;max-width:680px;background:#f7f6f2;border:1px solid #bab9b2">
<tr><td style="padding:12px 24px;border-bottom:1px solid #bab9b2;font:10px/1.6 Arial,sans-serif;letter-spacing:1px;text-transform:uppercase">Est. 2026 &nbsp; · &nbsp; {e(date)} &nbsp; · &nbsp; {e(edition)}</td></tr>
<tr><td align="center" style="padding:28px 16px 24px"><p style="margin:0;font:10px Arial,sans-serif;letter-spacing:3px;text-transform:uppercase">WeAware presents</p><h1 style="font:bold 48px/1 Georgia,'Times New Roman',serif;letter-spacing:-2px;margin:12px 0">The Crosscheck</h1><p style="margin:0;font:13px/1.6 Georgia,serif">The feed, distilled. Disagreement kept in.</p></td></tr>
<tr><td style="height:4px;border-top:3px solid #17191b;border-bottom:1px solid #17191b;font-size:0">&nbsp;</td></tr>
<tr><td style="padding:12px 24px;border-bottom:1px solid #bab9b2;font:11px Arial,sans-serif;letter-spacing:1px;text-transform:uppercase">Section A &nbsp; / &nbsp; The front page &nbsp; / &nbsp; {len(articles[:8])} stories</td></tr>
{''.join(cards)}
<tr><td style="padding:24px;font:12px/1.8 Arial,sans-serif;color:#585b59"><strong style="color:#17191b">WeAware · The Crosscheck</strong><br>Cross-checked by agents. Sources always shown.<br>{e(note)}<br>Reply to this email to reach WeAware.<br><a href="{e(unsub)}" style="color:#17191b;text-decoration:underline">Unsubscribe from email briefings</a></td></tr>
</table></td></tr></table></body></html>'''
    plain += [note, 'Reply to this email to reach WeAware.', 'Unsubscribe: ' + unsub]
    return html, '\n\n'.join(plain)
