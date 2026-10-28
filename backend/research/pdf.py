"""Render an approved investigation as a private, text-selectable PDF.

No network access or AI calls. Body citations link to the source notebook;
references link to original documents. Rendering never changes reviewed content.
"""
from io import BytesIO
from pathlib import Path
from html import escape
import math
import re
import threading
from urllib.parse import urlsplit

from .lengths import LENGTHS, report_words

_FONT_LOCK = threading.Lock()


def _fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    with _FONT_LOCK:
        if 'JeffSans' not in pdfmetrics.getRegisteredFontNames():
            folder = Path(__file__).with_name('fonts')
            pdfmetrics.registerFont(TTFont('JeffSans', str(folder / 'DejaVuSans.ttf')))
            pdfmetrics.registerFont(TTFont('JeffSansBold', str(folder / 'DejaVuSans-Bold.ttf')))
            pdfmetrics.registerFontFamily('JeffSans', normal='JeffSans', bold='JeffSansBold', italic='JeffSans', boldItalic='JeffSansBold')


def _plain(value):
    # Normalize unusual spaces/dashes; strip control characters. All user/model
    # strings are subsequently XML-escaped, never interpreted as report markup.
    text = str(value or '').translate(str.maketrans({'\u2011': '-', '\u2013': '-', '\u2014': ' - ', '\u00a0': ' ', '\u202f': ' '}))
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)


def _safe_link(value):
    url = str(value or '')
    try:
        parsed = urlsplit(url)
        if parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password and len(url) <= 2048:
            return url
    except ValueError:
        pass
    return None


def render_report_pdf(investigation):
    if investigation.get('status') != 'completed' or not investigation.get('report'):
        raise ValueError('Only editor-approved reports can be exported')
    _fonts()
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, HRFlowable

    report = investigation['report']
    ink, muted, accent = colors.HexColor('#202726'), colors.HexColor('#646b69'), colors.HexColor('#a54e32')
    styles = {
        'eyebrow': ParagraphStyle('eyebrow', fontName='JeffSansBold', fontSize=8, leading=12, textColor=accent, spaceAfter=12),
        'title': ParagraphStyle('title', fontName='JeffSans', fontSize=25, leading=31, textColor=ink, spaceAfter=14),
        'answer': ParagraphStyle('answer', fontName='JeffSans', fontSize=12, leading=18, textColor=ink, spaceAfter=12),
        'heading': ParagraphStyle('heading', fontName='JeffSansBold', fontSize=13, leading=19, spaceBefore=17, spaceAfter=9, textColor=ink, keepWithNext=True),
        'body': ParagraphStyle('body', fontName='JeffSans', fontSize=10.5, leading=16.5, spaceAfter=10, alignment=TA_LEFT, textColor=ink, splitLongWords=True),
        'small': ParagraphStyle('small', fontName='JeffSans', fontSize=8, leading=12, textColor=muted, spaceAfter=6, splitLongWords=True),
        'reference': ParagraphStyle('reference', fontName='JeffSans', fontSize=9, leading=13.5, textColor=ink, spaceAfter=5, splitLongWords=True),
    }

    def paragraph(value, style='body', suffix=''):
        return Paragraph(escape(_plain(value)) + suffix, styles[style])

    sources = report.get('sources', [])
    numbers = {source['id']: i for i, source in enumerate(sources, 1)}
    claims = {claim['id']: claim for claim in report.get('claims', [])}
    word_count = report_words(report)
    length = LENGTHS.get(investigation.get('reportLength', report.get('reportLength', 'standard')), LENGTHS['standard'])
    minutes = max(1, math.ceil(word_count / 220))
    cutoff = _plain(report.get('cutoff', 'Not recorded')).replace('T', ' ').replace('+00:00', ' UTC')
    cutoff = re.sub(r'\.\d+(?= UTC|Z|$)', '', cutoff)
    story = [paragraph('WEAWARE / SHERLOCK MODE / JOURNALIST JEFF', 'eyebrow'),
             paragraph(report['title'], 'title'),
             paragraph('%s report  |  %s words of analysis  |  About %s min read' % (length['label'], word_count, minutes), 'small'),
             paragraph('Private research brief - editor approved. Research cutoff: ' + cutoff, 'small'),
             HRFlowable(width='100%', thickness=0.7, color=accent, spaceBefore=7, spaceAfter=16),
             paragraph('The question', 'heading'), paragraph(investigation.get('question', report['title']))]
    if investigation.get('scope'):
        story.append(paragraph('Scope: ' + investigation['scope'], 'small'))
    story += [paragraph('The answer at a glance', 'heading'), paragraph(report.get('answer', ''), 'answer')]
    for section in report['sections']:
        story.append(paragraph(section['heading'], 'heading'))
        for item in section['paragraphs']:
            refs = set()
            for claim_id in item['claimIds']:
                claim = claims[claim_id]
                for evidence in claim['evidence']:
                    refs.add(numbers[evidence['sourceId']])
            citations = ' <super>' + ' '.join('<link href="#source-%s" color="#a54e32">[%s]</link>' % (number, number) for number in sorted(refs)) + '</super>'
            story.append(paragraph(item['text'], suffix=citations))
    for heading, field in [('What remains unknown', 'unknowns'), ('Research limitations', 'limitations')]:
        story.append(paragraph(heading, 'heading'))
        for item in report.get(field, []):
            story.append(paragraph('- ' + item))
    story.append(paragraph('Research used accessible web text. %s candidate sources were unavailable or duplicates. Selected source passages and the full evidence map can be inspected in your private website report.' % report.get('retrievalGaps', 0), 'small'))
    story.append(paragraph('Source notebook', 'heading'))
    story.append(paragraph('Bracketed numbers in the analysis point to these references. Source titles are clickable links to the original documents. References do not count toward the requested analysis length.', 'small'))
    for number, source in enumerate(sources, 1):
        title = escape(_plain(source.get('title', source['id'])))
        url = _safe_link(source.get('url'))
        label = '<a name="source-%s"/>[%s] ' % (number, number)
        label += '<link href="%s" color="#a54e32">%s</link>' % (escape(url, quote=True), title) if url else title
        parts = [Paragraph(label, styles['reference'])]
        details = '%s | Published: %s' % (source.get('publisherHost', ''), source.get('publishedAt') or 'date not available')
        parts.append(paragraph(details, 'small'))
        if url:
            parsed = urlsplit(url)
            display = parsed.hostname + parsed.path
            if len(display) > 145:
                display = display[:142] + '...'
            if parsed.query:
                display += ' (link includes query parameters)'
            parts.append(paragraph(display, 'small'))
        # Keep each compact reference together; the notebook can flow onto the
        # next page rather than shrinking type or producing a separate cover.
        story.extend([KeepTogether(parts), Spacer(1, 7)])
    story += [Spacer(1, 12), HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#d8dcda'), spaceAfter=10),
              paragraph(report.get('disclosure', 'Prepared by Journalist Jeff, an AI assistant, and reviewed by a WeAware pilot editor. Research may be incomplete or contain errors.'), 'small')]

    def page_frame(canvas, doc):
        width, height = A4
        canvas.saveState()
        canvas.setFont('JeffSans', 7.5)
        canvas.setFillColor(muted)
        if doc.page > 1:
            canvas.drawString(52, height-32, 'WEAWARE / SHERLOCK MODE')
        canvas.setStrokeColor(colors.HexColor('#d8dcda'))
        canvas.setLineWidth(0.4)
        canvas.line(52, 40, width-52, 40)
        canvas.drawString(52, 27, 'Private research brief | Journalist Jeff')
        canvas.drawRightString(width-52, 27, 'Page %s' % doc.page)
        canvas.restoreState()

    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, rightMargin=52, leftMargin=52, topMargin=50, bottomMargin=55,
                                 title=_plain(report['title']), author='WeAware / Journalist Jeff',
                                 subject='Private, editor-approved research brief', pageCompression=1)
    document.build(story, onFirstPage=page_frame, onLaterPages=page_frame)
    return output.getvalue()
