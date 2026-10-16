"""Extract short reports and export a reproducible, readable workload assessment."""
import io
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak
from .assessment import Description, WorkloadPlan, calculate

MAX_BYTES = 5 * 1024 * 1024


def extract_report(data: bytes, name: str):
    if not data or len(data) > MAX_BYTES:
        raise ValueError('Choose a PDF smaller than 5 MB.')
    if not data.startswith(b'%PDF-'):
        raise ValueError('This file is not a readable PDF. Choose a PDF report.')
    name = name.replace('\\', '/').split('/')[-1][:150].strip() or 'report.pdf'
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError('This PDF is password protected. Upload an unlocked copy.')
        if not 1 <= len(reader.pages) <= 10:
            raise ValueError('Use a PDF with 1-10 pages. Split a longer report into a relevant extract.')
        parts = []
        for index, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or '').strip()
            if not text:
                raise ValueError(f'Page {index} has no readable text. Scanned/image pages need OCR before uploading.')
            parts.append(f'[Page {index}]\n{text}')
        text = '\n\n'.join(parts)
        if len(text) < 50:
            raise ValueError('This PDF contains too little readable text. Add a more detailed report.')
        if len(text) > 40000:
            raise ValueError('This report has too much text. Use an extract under 40,000 characters.')
        return {'name': name, 'text': text, 'pages': len(reader.pages)}
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('The PDF could not be read. Try exporting a new, unlocked text-based PDF.') from exc


def fonts():
    regular = Path('C:/Windows/Fonts/arial.ttf')
    bold = Path('C:/Windows/Fonts/arialbd.ttf')
    if not regular.exists():
        regular = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
        bold = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
    if regular.exists() and bold.exists():
        if 'SwayBody' not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont('SwayBody', str(regular)))
            pdfmetrics.registerFont(TTFont('SwayBold', str(bold)))
            pdfmetrics.registerFontFamily('SwayBody', normal='SwayBody', bold='SwayBold', italic='SwayBody', boldItalic='SwayBold')
        return 'SwayBody', 'SwayBold'
    return 'Helvetica', 'Helvetica-Bold'


def render_assessment(plan: WorkloadPlan, description: Description, model: str = ''):
    result = calculate(plan)  # Never trust a client-supplied verdict or total.
    regular, bold = fonts()
    green, muted, line = colors.HexColor('#214d3f'), colors.HexColor('#6d7f65'), colors.HexColor('#dfe6d8')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BodySway', fontName=regular, fontSize=9, leading=14, textColor=green, spaceAfter=8, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='SmallSway', parent=styles['BodySway'], fontSize=8, leading=12, textColor=muted))
    styles.add(ParagraphStyle(name='TitleSway', fontName=bold, fontSize=23, leading=29, textColor=green, spaceAfter=12))
    styles.add(ParagraphStyle(name='HeadingSway', fontName=bold, fontSize=12, leading=17, textColor=green, spaceBefore=17, spaceAfter=9, keepWithNext=True))
    def p(text, style='BodySway'):
        # Common LLM typography includes a nonbreaking hyphen absent from Arial.
        text = str(text).translate(str.maketrans({c: '-' for c in '\u2010\u2011\u2012\u2013\u2014\u2015'}))
        text = text.replace('\u00a0', ' ').replace('\u202f', ' ').replace('\u200b', '').replace('\u00ad', '')
        return Paragraph(escape(text).replace('\n', '<br/>'), styles[style])
    def heading(text):
        return p(text, 'HeadingSway')
    def table(rows, widths):
        data = [[p(cell, 'SmallSway') for cell in row] for row in rows]
        t = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#edf3e5')), ('VALIGN',(0,0),(-1,-1),'TOP'),
                               ('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),
                               ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),7),
                               ('LINEBELOW',(0,0),(-1,-1),.4,line)]))
        return t
    fmt = lambda n: f'{n:,.1f}'.removesuffix('.0')
    width = 174 * mm
    story = [p('SWAY / AI WORKLOAD ASSESSMENT', 'SmallSway'), p(plan.name, 'TitleSway'),
             p(datetime.now(timezone.utc).strftime('Prepared %d %B %Y, %H:%M UTC'), 'SmallSway')]
    verdict = {'decrease':'Human workload decreases under these assumptions.', 'increase':'Human workload increases under these assumptions.', 'unchanged':'Recurring human workload stays about the same.'}[result['verdict']]
    story += [heading(verdict), table([['Today', 'With AI', 'Weekly difference'],
              [f"{fmt(result['current_hours'])} hours", f"{fmt(result['after_hours'])} hours", f"{fmt(abs(result['saved_hours']))} hours {'freed' if result['saved_hours'] >= 0 else 'added'} ({fmt(abs(result['change_percent']))}%)"]], [width/3]*3),
              Spacer(1,10), p('Conditional estimate at equal weekly demand. Human effort freed is available capacity, not payroll savings. Validate assumptions with a pilot.', 'SmallSway'),
              heading('What was analyzed'), p(plan.summary), heading('Your descriptions'), p('Current process: '+(description.current_process or 'Provided in attached reports.')), p('Proposed AI change: '+(description.ai_change or 'Provided in attached reports.'))]
    if description.documents:
        story += [heading('Source reports')]
        for doc in description.documents:
            story.append(p(f'{doc.name} - {doc.pages} pages; {len(doc.text):,} extracted characters. Source text is used for analysis; full reports are not reproduced here.'))
    story += [heading('Inputs used in the calculation'), table([['Input', 'Value'],
        ['Items per week', fmt(plan.weekly_volume)], ['Items using AI', fmt(plan.adoption_percent)+'%'],
        ['Added checking per AI item', fmt(plan.review_minutes)+' min'], ['AI items needing extra corrections', fmt(plan.correction_percent)+'%'],
        ['Extra time per correction', fmt(plan.correction_minutes)+' min'], ['Ongoing overhead', fmt(plan.weekly_overhead_hours)+' hours/week'],
        ['One-time setup', fmt(plan.setup_hours)+' hours']], [width*.66,width*.34]), heading('Original human tasks per item'),
        table([['Task', 'Today (min)', 'Remaining with AI (min)']]+[[t.name,fmt(t.current_minutes),fmt(t.remaining_minutes)] for t in plan.tasks], [width*.54,width*.21,width*.25])]
    for task in plan.tasks:
        story.append(p(f'{task.name}: {task.explanation}', 'SmallSway'))
    labels = {'unchanged_work':'Items handled without AI','remaining_work':'Original human work remaining','checking':'Added AI checking','corrections':'Extra corrections','ongoing_overhead':'Monitoring and maintenance'}
    story += [heading('Where the weekly work goes'), table([['Human work after AI', 'Hours/week']]+[[labels[k],fmt(v)] for k,v in result['breakdown'].items()], [width*.7,width*.3]), PageBreak(), heading('Break-even and setup effort')]
    threshold = result['max_review_minutes_to_break_even']
    story.append(p('No AI-assisted items: no per-item review threshold.' if threshold is None else 'Remaining work, corrections and overhead already exceed the baseline, even with no added checking.' if threshold<0 else f'With other inputs fixed, added checking breaks even at approximately {threshold:.2f} minutes per AI item.'))
    payback = result['setup_payback_weeks']
    story += [p(f"First-week human effort including setup: {fmt(result['first_week_hours'])} hours."), p('No setup payback while recurring savings are zero or negative.' if payback is None else f'Equivalent recurring savings recover setup effort in approximately {fmt(payback)} weeks.'),
              heading('Sensitivity to checking and correction effort'), p('Only checking and correction time vary below; these are scenario comparisons, not statistical confidence intervals.', 'SmallSway'),
              table([['Scenario', 'Hours/week with AI', 'Hours freed (+) / added (-)']]+[[f"{s['label']} ({s['factor']}x)",fmt(s['after_hours']),fmt(s['saved_hours'])] for s in result['scenarios']], [width*.4,width*.3,width*.3]),
              heading('Original AI assumptions and questions'), p('These notes describe the AI draft. The editable inputs above are the values used in this export; notes may differ after manual edits.', 'SmallSway')]
    for item in [*plan.assumptions,*plan.questions]: story.append(p('- '+item))
    story += [heading('Risks to validate')]
    for item in plan.risks: story.append(p('- '+item))
    story.append(KeepTogether([heading('Pilot steps')]+[p(f'{index}. {item}') for index,item in enumerate(plan.pilot_steps,1)]))
    story += [heading('How the assessment works'), p('The LLM reads descriptions and report text, identifies tasks and proposes assumptions. You review or edit the inputs. Python calculates totals and the workload verdict; it does not ask the LLM to guess a savings percentage.'), p(result['formula']), p(result['scope']), p('Calculation version: workload-1.0. Analysis model: '+(model or 'not supplied'), 'SmallSway')]
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(210*mm,297*mm), leftMargin=18*mm, rightMargin=18*mm, topMargin=20*mm, bottomMargin=20*mm, title='Sway - '+plan.name, author='Sway')
    def page_footer(canvas, document):
        canvas.saveState(); canvas.setStrokeColor(line); canvas.line(18*mm,15*mm,192*mm,15*mm)
        canvas.setFont(regular,8); canvas.setFillColor(muted); canvas.drawString(18*mm,10*mm,'Sway | Conditional workload estimate'); canvas.drawRightString(192*mm,10*mm,f'Page {document.page}'); canvas.restoreState()
    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    return buffer.getvalue()
