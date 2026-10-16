import json
import pytest
from fastapi.testclient import TestClient
from app import main, ai, decisions
from app.storage import LocalStore
from app.decision_store import DecisionStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'store', LocalStore(tmp_path / 'cases.db'))
    monkeypatch.setenv('GROQ_DAILY_CALL_LIMIT', '100')
    return TestClient(main.app)


@pytest.fixture
def model(monkeypatch):
    result = {'summary':'The whole workspace is unavailable.', 'action':'route', 'priority':'high', 'team':'Technical Support',
              'rationale':'The case reports a service outage affecting all members. The outage rule assigns high priority to Technical Support.',
              'policy_rule_ids':['P2','P3'], 'evidence':[{'source_id':'case','quote':'all 24 members of our workspace get a 503 error','supports':'Multiple users cannot access the product.'}],
              'missing_information':[], 'uncertainties':[], 'requires_review':False, 'response_draft':'We have recorded this issue for technical investigation.'}
    calls=[]
    async def completion(*args):
        calls.append(args)
        return result, {'model':'test-model','tokens':123,'provider':'test'}
    monkeypatch.setattr(ai,'completion',completion)
    return result,calls


def create(client, workflow=None):
    sample = decisions.SAMPLES[0]
    payload={k:sample[k] for k in ('title','text','documents')}
    payload['workflow']=workflow or decisions.DecisionWorkflow().model_dump()
    response=client.post('/api/decisions/cases',json=payload)
    assert response.status_code==200
    return response.json()


def run(client, case):
    return client.post(f"/api/decisions/cases/{case['id']}/run")


def test_actual_model_decision_executes_and_persists_once(client,model):
    case=create(client)
    response=run(client,case)
    assert response.status_code==200
    saved=response.json()
    assert saved['status']=='executed'
    assert saved['local_state']['team']=='Technical Support'
    assert saved['local_state']['priority']=='high'
    assert saved['local_state']['status']=='routed'
    assert saved['meta']['tokens']==123
    assert saved['meta']['elapsed_ms']>=0
    assert len(model[1])==1
    sent=model[1][0][1]
    assert sent['sources'][0]['text']==case['text']
    assert sent['sources'][1]['text']==case['documents'][0]['text']
    assert sent['policy_rules'][1]['id']=='P2'
    assert run(client,case).status_code==409
    assert len(model[1])==1
    restored=DecisionStore(main.store).get(case['id'])
    assert restored==saved
    assert [e['kind'] for e in saved['events']]==['case_created','model_requested','model_decided','python_validated','action_executed']
    assert client.get(f"/api/decisions/cases/{case['id']}/audit").json()['valid']
    exported=client.get(f"/api/decisions/cases/{case['id']}/export").json()
    assert exported['audit_verification']['valid']
    assert exported['decision']==model[0]


@pytest.mark.parametrize('change', ['quote','team','rule','request_info','resolve'])
def test_invalid_evidence_or_action_is_blocked_and_cannot_be_approved(client,model,change):
    decision,_=model
    if change=='quote': decision['evidence'][0]['quote']='this quote does not exist in the case'
    if change=='team': decision['team']='Administrators'
    if change=='rule': decision['policy_rule_ids']=['P999']
    if change=='request_info': decision.update(action='request_info',missing_information=[])
    if change=='resolve': decision.update(action='resolve',missing_information=['Confirmation'])
    case=create(client)
    saved=run(client,case).json()
    assert saved['status']=='blocked'
    assert saved['local_state']['status']=='new'
    assert not any(e['kind']=='action_executed' for e in saved['events'])
    assert client.post(f"/api/decisions/cases/{case['id']}/review",json={'verdict':'approve','reason':'I want to force this action'}).status_code==409


@pytest.mark.parametrize('gate', ['workflow','action','priority','uncertainty','model','escalate'])
def test_review_gates_delay_execution_then_approval_executes_once(client,model,gate):
    workflow=decisions.DecisionWorkflow().model_dump()
    decision,_=model
    if gate=='workflow': workflow['auto_execute']=False
    if gate=='action': workflow['review_actions']=['route']
    if gate=='priority': decision['priority']='critical'
    if gate=='uncertainty': decision['uncertainties']=['The cause has not been confirmed.']
    if gate=='model': decision['requires_review']=True
    if gate=='escalate': decision['action']='escalate'
    case=create(client,workflow)
    saved=run(client,case).json()
    assert saved['status']=='review_required'
    assert saved['local_state']['status']=='new'
    review_url=f"/api/decisions/cases/{case['id']}/review"
    assert client.post(review_url,json={'verdict':'approve','reason':'short'}).status_code==422
    response=client.post(review_url,json={'verdict':'approve','reason':'Evidence supports this local routing action.'})
    assert response.status_code==200
    assert response.json()['status']=='executed'
    assert response.json()['local_state']['team']=='Technical Support'
    assert client.post(review_url,json={'verdict':'approve','reason':'Duplicate approval must not run again.'}).status_code==409


def test_rejection_preserves_original_state(client,model):
    model[0]['requires_review']=True
    case=create(client)
    run(client,case)
    saved=client.post(f"/api/decisions/cases/{case['id']}/review",json={'verdict':'reject','reason':'This needs further investigation first.'}).json()
    assert saved['status']=='rejected'
    assert saved['local_state']['status']=='new'


def test_policy_snapshot_is_immutable_when_workspace_changes(client,model):
    case=create(client)
    changed=decisions.DecisionWorkflow(name='A different policy',policy='Always request more information before routing.').model_dump()
    assert client.post('/api/decisions/setup',json=changed).status_code==200
    assert client.get('/api/decisions/setup').json()['workflow']==changed
    assert run(client,case).json()['workflow']==case['workflow']


def test_provider_failure_is_persisted_and_retryable(client,model,monkeypatch):
    original=ai.completion
    async def failure(*args): raise ai.AIUnavailable('Provider unavailable')
    monkeypatch.setattr(ai,'completion',failure)
    case=create(client)
    assert run(client,case).status_code==503
    saved=client.get(f"/api/decisions/cases/{case['id']}").json()
    assert saved['status']=='failed'
    assert saved['local_state']['status']=='new'
    monkeypatch.setattr(ai,'completion',original)
    assert run(client,case).json()['status']=='executed'


def test_unknown_action_is_rejected_before_execution(client,model):
    model[0]['action']='run_shell'
    case=create(client)
    assert run(client,case).status_code==503
    assert client.get(f"/api/decisions/cases/{case['id']}").json()['local_state']['status']=='new'


def test_cap_and_concurrency_do_not_execute(client,model,monkeypatch):
    case=create(client)
    with main.decision_lock:
        assert run(client,case).status_code==409
    monkeypatch.setenv('GROQ_DAILY_CALL_LIMIT','0')
    assert run(client,case).status_code==429
    assert not model[1]
    assert client.get(f"/api/decisions/cases/{case['id']}").json()['status']=='failed'


def test_audit_detects_changed_events_and_source(client,model):
    case=create(client)
    run(client,case)
    repository=DecisionStore(main.store)
    with main.store.connect() as db:
        row=db.execute('SELECT payload FROM decision_events WHERE case_id=? AND seq=1',(case['id'],)).fetchone()
        event=json.loads(row['payload']);event['data']['workflow']='tampered'
        db.execute('UPDATE decision_events SET payload=? WHERE case_id=? AND seq=1',(json.dumps(event),case['id']))
    assert not repository.audit(case['id'])['valid']


def test_restart_recovers_interrupted_case(client):
    case=create(client)
    repository=DecisionStore(main.store)
    repository.begin(case['id'])
    repository.recover()
    recovered=repository.get(case['id'])
    assert recovered['status']=='failed'
    assert recovered['local_state']['status']=='new'
    repository.begin(case['id'])


def test_input_bounds_and_unknown_fields(client):
    assert client.post('/api/decisions/cases',json={'title':'Hi','text':'x','workflow':{}}).status_code==422
    assert client.post('/api/decisions/setup',json={'teams':['Billing','Billing']}).status_code==422
    assert client.get('/api/decisions/cases/missing').status_code==404
    assert client.post('/api/decisions/cases/missing/run').status_code==404


def test_request_info_executes_real_local_draft(client,model):
    model[0].update(action='request_info',missing_information=['Workspace ID'],response_draft='Please share the workspace ID.')
    case=create(client)
    saved=run(client,case).json()
    assert saved['local_state']['status']=='awaiting_information'
    assert saved['local_state']['response_draft']=='Please share the workspace ID.'


def test_resolution_can_execute_when_explicitly_authorized(client,model):
    model[0].update(action='resolve')
    workflow=decisions.DecisionWorkflow(review_actions=[]).model_dump()
    saved=run(client,create(client,workflow)).json()
    assert saved['status']=='executed'
    assert saved['local_state']['status']=='resolved'
