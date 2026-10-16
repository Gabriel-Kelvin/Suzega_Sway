import csv
import hashlib
import io
import json
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Query
from starlette.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from .models import ExperimentConfig, AIRequest, BriefRequest
from .simulation import compare, VERSION
from .storage import LocalStore
from . import ai
from . import decisions
from . import assessment
from . import assessment_pdf
from .decision_store import DecisionStore, CaseConflict

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
store = LocalStore(ROOT / os.getenv('DATABASE_PATH', 'data/sway.db'))
@asynccontextmanager
async def lifespan(app):
    DecisionStore(store).recover()
    yield


app = FastAPI(title='Sway AI Workload Assessment', version='0.3.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:5173', 'http://localhost:5173'], allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])
simulation_lock = threading.Lock()
decision_lock = threading.Lock()


def case_store():
    return DecisionStore(store)


@app.get('/api/decisions/setup')
def decision_setup():
    return {'workflow': case_store().settings() or decisions.DecisionWorkflow().model_dump(), 'samples': decisions.SAMPLES}


@app.post('/api/decisions/setup')
def save_decision_setup(workflow: decisions.DecisionWorkflow):
    return case_store().save_settings(workflow.model_dump())


@app.post('/api/decisions/setup/draft')
async def draft_decision_setup(request: decisions.WorkflowDescription):
    reserve('decision_workflow')
    try:
        return await decisions.draft_workflow(request.description)
    except ai.AIUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get('/api/decisions/cases')
def list_cases():
    return case_store().list()


@app.post('/api/decisions/cases')
def create_case(request: decisions.NewCase):
    return case_store().create(request.model_dump())


@app.get('/api/decisions/cases/{id}')
def get_case(id: str):
    try:
        return case_store().get(id)
    except KeyError:
        raise HTTPException(404, 'Case not found')


@app.post('/api/decisions/cases/{id}/run')
async def run_case(id: str):
    if not decision_lock.acquire(blocking=False):
        raise HTTPException(409, 'A case is already being analyzed. Wait for it to finish before starting another.')
    repository = case_store()
    started = False
    try:
        case = repository.begin(id)
        started = True
        reserve('case_decision')
        decision, meta = await decisions.decide(case)
        return repository.finish(id, decision, meta)
    except KeyError:
        raise HTTPException(404, 'Case not found')
    except CaseConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ai.AIUnavailable as exc:
        if started:
            repository.fail(id, str(exc))
        raise HTTPException(503, str(exc)) from exc
    except HTTPException as exc:
        if started:
            repository.fail(id, str(exc.detail))
        raise
    except BaseException as exc:
        if started:
            repository.fail(id, 'The decision run was interrupted. No action was executed. Retry this case.')
        raise
    finally:
        decision_lock.release()


@app.post('/api/decisions/cases/{id}/review')
def review_case(id: str, review: decisions.Review):
    try:
        return case_store().review(id, review.verdict, review.reason)
    except KeyError:
        raise HTTPException(404, 'Case not found')
    except CaseConflict as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get('/api/decisions/cases/{id}/export')
def export_case(id: str):
    try:
        repository = case_store()
        case = repository.get(id)
        case['audit_verification'] = repository.audit(id)
        return Response(json.dumps(case, indent=2), media_type='application/json', headers={'Content-Disposition': f'attachment; filename="sway-case-{id[:8]}.json"'})
    except KeyError:
        raise HTTPException(404, 'Case not found')


@app.get('/api/decisions/cases/{id}/audit')
def audit_case(id: str):
    try:
        return case_store().audit(id)
    except KeyError:
        raise HTTPException(404, 'Case not found')


@app.get('/api/health')
def health():
    return {'status': 'ok', 'storage': 'local SQLite', 'engine': VERSION, 'ai_configured': bool(os.getenv('GROQ_API_KEY')), 'ai_model': os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b')}


@app.get('/api/defaults')
def defaults():
    return ExperimentConfig().model_dump()


@app.post('/api/experiments')
def run(config: ExperimentConfig):
    if config.daily_cases * config.days * len(config.stages) * config.repetitions > 350000:
        raise HTTPException(422, 'This local experiment is too large. Reduce days, daily cases, stages, or repetitions.')
    if not simulation_lock.acquire(blocking=False):
        raise HTTPException(409, 'An experiment is already running. Please wait for it to finish.')
    try:
        result = compare(config)
        canonical = json.dumps(config.model_dump(), sort_keys=True, separators=(',', ':'))
        result['input_hash'] = hashlib.sha256(canonical.encode()).hexdigest()
        return store.save(result)
    finally:
        simulation_lock.release()


@app.get('/api/experiments')
def history():
    return store.list()


def get_experiment(id):
    result = store.get(id)
    if not result:
        raise HTTPException(404, 'Experiment not found')
    return result


@app.get('/api/experiments/{id}')
def get(id: str):
    return get_experiment(id)


@app.get('/api/experiments/{id}/export')
def export(id: str, format: str = 'json'):
    result = get_experiment(id)
    if format == 'csv':
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['arrangement', 'metric', 'mean', 'p10', 'p90'])
        for s in result['strategies']:
            for key, value in s['metrics'].items():
                writer.writerow([s['name'], key, value['mean'], value['low'], value['high']])
        return Response(buf.getvalue(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="sway-results.csv"'})
    if format == 'brief':
        c = result['config']
        lines = [f"# {c['name']} — pilot brief", '', 'Synthetic scenario exploration. Validate assumptions before using for business decisions.', '',
                 f"Engine: {result['engine_version']} | Runs: {c['repetitions']} | Seed: {c['seed']}", f"Input SHA-256: {result['input_hash']}", '', '## Results', '',
                 '| Arrangement | Mean turnaround (elapsed h) | End backlog | Human service h | SLA % |', '|---|---:|---:|---:|---:|']
        for s in result['strategies']:
            m = s['metrics']
            lines.append(f"| {s['name']} | {m['mean_hours']['mean']:.1f} | {m['backlog']['mean']:.0f} | {m['human_hours']['mean']:.1f} | {m['sla_percent']['mean']:.1f} |")
        lines += ['', '## What to validate', '', '- Measure case arrivals and task-duration distributions for at least two representative weeks.', '- Test whether AI-prepared evidence reduces review time without reducing decision quality.', '- Measure escalation rates and include rare, high-impact exceptions.', '- Agree human approval boundaries and working-hour protections with the team.', '', '## Six-week pilot', '', '1. Weeks 1–2: observe the baseline, validate the process model, define quality and safety acceptance criteria.', '2. Weeks 3–4: run AI preparation in shadow mode; compare against human work.', '3. Week 5: trial a bounded cohort with mandatory human decisions and rollback.', '4. Week 6: compare measured outcomes with assumptions and decide whether to expand.', '', '## Method and limitations', '', *[f'- {v}' for v in result['methodology']['limitations']], '', '## Assumptions', '', '```json', json.dumps(c, indent=2), '```']
        return Response('\n'.join(lines), media_type='text/markdown', headers={'Content-Disposition': 'attachment; filename="sway-pilot-brief.md"'})
    if format != 'json':
        raise HTTPException(422, 'Choose json, csv, or brief')
    return Response(json.dumps(result, indent=2), media_type='application/json', headers={'Content-Disposition': 'attachment; filename="sway-experiment.json"'})


def reserve(kind):
    if not store.reserve_ai_call(int(os.getenv('GROQ_DAILY_CALL_LIMIT', '30')), kind):
        raise HTTPException(429, 'The local daily AI request cap was reached. You can still recalculate an existing assessment.')


@app.post('/api/ai/draft')
async def draft(request: AIRequest):
    reserve('draft')
    try:
        return await ai.draft(request.prompt, request.config)
    except ai.AIUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post('/api/ai/brief')
async def brief(request: BriefRequest):
    experiment = get_experiment(request.experiment_id)
    reserve('brief')
    try:
        return await ai.brief(experiment)
    except ai.AIUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


# Shared workload API used by the standalone deployment entry point as well.
from .workload_api import router as workload_router
app.state.reserve = reserve
app.include_router(workload_router)
