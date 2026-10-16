import asyncio
import pytest
import httpx
from app import ai
from app.models import ExperimentConfig


@pytest.mark.parametrize('narrative', ['Cut time by 50%', 'Halves the turnaround', 'Twice the work in 2 hours'])
def test_numerical_ai_claims_are_rejected(monkeypatch, narrative):
    async def completion(*args):
        return {'questions':[narrative],'pilot_plan':['Validate in shadow mode.']}, {}
    monkeypatch.setattr(ai, 'completion', completion)
    with pytest.raises(ai.AIUnavailable):
        asyncio.run(ai.brief({'config':{}, 'strategies':[], 'methodology':{}}))


@pytest.mark.parametrize('status', [401, 429, 500])
def test_provider_error_does_not_leak_response(monkeypatch, status):
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            return httpx.Response(status, text='secret diagnostic must not escape')
    monkeypatch.setenv('GROQ_API_KEY', 'test-only-placeholder')
    monkeypatch.setattr(ai.httpx, 'AsyncClient', Client)
    with pytest.raises(ai.AIUnavailable) as caught:
        asyncio.run(ai.completion('test', {}))
    assert 'secret diagnostic' not in str(caught.value)


def test_unapproved_model_is_never_called(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'test-only-placeholder')
    monkeypatch.setenv('GROQ_MODEL', 'unapproved')
    with pytest.raises(ai.AIUnavailable, match='allowlist'):
        asyncio.run(ai.completion('test', {}))


def test_brief_observations_are_computed_not_generated(monkeypatch):
    async def completion(*args):
        return {'questions':['Does review quality hold?'], 'pilot_plan':['Run in shadow mode.']}, {'model':'test'}
    monkeypatch.setattr(ai, 'completion', completion)
    def strategy(id, hours):
        return {'id':id,'name':id,'metrics':{'mean_hours':{'mean':hours},'human_hours':{'mean':20},'backlog':{'mean':3}}}
    experiment={'config':{'assist_multiplier':.75},'strategies':[strategy('current',100),strategy('automated',80),strategy('augmented',40)],'methodology':{}}
    result = asyncio.run(ai.brief(experiment))
    assert '100.0 elapsed hours today' in result['observations'][0]
    assert '25%' in result['observations'][1]
    assert 'equal accuracy is not established' in result['observations'][1]
