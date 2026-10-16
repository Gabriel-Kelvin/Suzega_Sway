from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from . import ai, assessment, assessment_pdf

router = APIRouter()


@router.post('/api/assessment/documents')
async def upload_workload_report(request: Request, name: str = Query(default='report.pdf', max_length=150)):
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > assessment_pdf.MAX_BYTES:
            raise HTTPException(413, 'Choose a PDF smaller than 5 MB.')
    try:
        return await run_in_threadpool(assessment_pdf.extract_report, bytes(data), name)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post('/api/assessment/export')
def export_workload(request: assessment.AssessmentExport):
    try:
        pdf = assessment_pdf.render_assessment(request.plan, request.description, request.model)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return Response(pdf, media_type='application/pdf', headers={'Content-Disposition': 'attachment; filename="sway-workload-assessment.pdf"'})


@router.post('/api/assessment/analyze')
async def analyze_workload(payload: assessment.Description, request: Request):
    request.app.state.reserve('workload_assessment')
    try:
        return await assessment.analyze(payload)
    except ai.AIUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post('/api/assessment/calculate')
def calculate_workload(plan: assessment.WorkloadPlan):
    try:
        return {'plan': plan.model_dump(), 'result': assessment.calculate(plan)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


