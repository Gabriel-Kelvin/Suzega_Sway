import io
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas
from app import main
from app.assessment import Description
from app.assessment_pdf import extract_report, render_assessment, MAX_BYTES
from app.storage import LocalStore
from test_assessment import plan


def report(pages=3, blank=False):
    out = io.BytesIO()
    canvas = Canvas(out)
    for i in range(pages):
        if not blank:
            canvas.drawString(50,750,f'Page {i+1}: Support workload: 200 requests daily, five days weekly, 15 human minutes per request.')
        canvas.showPage()
    canvas.save()
    return out.getvalue()


def test_extracts_all_report_pages_with_explicit_page_markers():
    document = extract_report(report(), '../../my-report.pdf')
    assert document['pages'] == 3
    assert document['name'] == 'my-report.pdf'
    assert '[Page 3]' in document['text']
    assert '200 requests' in document['text']
    assert Description(documents=[document]).current_process == ''


@pytest.mark.parametrize('data,message', [(b'not pdf','not a readable PDF'),(b'%PDF-'+b'x'*MAX_BYTES,'smaller than'),
    (report(11),'1-10 pages'),(report(blank=True),'OCR')], ids=['invalid-pdf','oversized','too-many-pages','scanned-page'])
def test_rejects_unusable_reports_without_silent_truncation(data,message):
    with pytest.raises(ValueError,match=message):
        extract_report(data,'report.pdf')


def test_encrypted_report_is_rejected():
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(report())))
    writer.encrypt('test-password')
    output = io.BytesIO(); writer.write(output)
    with pytest.raises(ValueError,match='password protected'):
        extract_report(output.getvalue(),'locked.pdf')


def test_export_contains_recomputed_totals_inputs_and_method():
    source=Description(documents=[extract_report(report(),'my-report.pdf')])
    pdf=render_assessment(plan(),source,'openai/gpt-oss-120b')
    assert pdf.startswith(b'%PDF-')
    reader=PdfReader(io.BytesIO(pdf))
    text='\n'.join(page.extract_text() for page in reader.pages)
    assert '197 hours' in text
    assert '53 hours freed' in text
    assert 'my-report.pdf' in text
    assert 'workload-1.0' in text
    assert 'Page 1' in text
    assert all(page.extract_text().strip() for page in reader.pages)


def test_report_api_and_pdf_export_without_ai_call(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'store',LocalStore(tmp_path/'pdf.db'))
    client=TestClient(main.app)
    parsed=client.post('/api/assessment/documents?name=three-pages.pdf',content=report(),headers={'Content-Type':'application/pdf'})
    assert parsed.status_code == 200
    payload={'plan':plan().model_dump(),'description':{'documents':[parsed.json()]},'model':'test'}
    exported=client.post('/api/assessment/export',json=payload)
    assert exported.status_code == 200
    assert exported.headers['content-type']=='application/pdf'
    assert '.pdf' in exported.headers['content-disposition']
    assert client.post('/api/assessment/export',json={**payload,'result':{'saved_hours':999}}).status_code==422
    assert client.post('/api/assessment/documents',content=b'bad').status_code==422
    assert client.post('/api/assessment/documents',content=b'x'*(MAX_BYTES+1)).status_code==413
