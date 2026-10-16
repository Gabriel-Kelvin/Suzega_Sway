import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from app import main, ai
from app.models import ExperimentConfig
from app.storage import LocalStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'store', LocalStore(tmp_path / 'test.db'))
    return TestClient(main.app)


def test_run_persist_restore_export(client, tmp_path):
    config = ExperimentConfig(days=5, daily_cases=10, repetitions=3).model_dump()
    response = client.post('/api/experiments', json=config)
    assert response.status_code == 200
    result = response.json()
    id = result['id']
    assert client.get('/api/experiments').json()[0]['id'] == id
    assert LocalStore(tmp_path / 'test.db').get(id) == result
    assert client.get(f'/api/experiments/{id}').json() == result
    assert client.get(f'/api/experiments/{id}/export').json() == result
    assert 'arrangement,metric,mean,p10,p90' in client.get(f'/api/experiments/{id}/export?format=csv').text
    assert 'What to validate' in client.get(f'/api/experiments/{id}/export?format=brief').text
    assert client.get(f'/api/experiments/{id}/export?format=bad').status_code == 422
    assert client.get('/api/experiments/missing').status_code == 404


def test_validation_and_concurrent_run(client):
    assert client.post('/api/experiments', json={'daily_cases': 999}).status_code == 422
    with main.simulation_lock:
        assert client.post('/api/experiments', json={}).status_code == 409
    assert client.post('/api/experiments', json={'days':40,'daily_cases':160,'repetitions':30}).status_code == 422


def test_missing_key_and_request_cap(client, monkeypatch):
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    monkeypatch.setenv('GROQ_DAILY_CALL_LIMIT', '1')
    data = {'prompt': 'Draft a claims workflow', 'config': ExperimentConfig().model_dump()}
    response = client.post('/api/ai/draft', json=data)
    assert response.status_code == 503
    assert 'GROQ_API_KEY' in response.json()['detail']
    assert client.post('/api/ai/draft', json=data).status_code == 429
    assert client.get('/api/health').json()['status'] == 'ok'


def test_invalid_ai_draft_never_applies(monkeypatch):
    async def invalid(*args):
        return {'summary': 'Invalid', 'assumptions': [], 'config': {'stages': []}}, {}
    monkeypatch.setattr(ai, 'completion', invalid)
    with pytest.raises(ai.AIUnavailable):
        asyncio.run(ai.draft('a test description', ExperimentConfig()))


def test_ai_cannot_change_experiment_sampling(monkeypatch):
    original = ExperimentConfig()
    edited = original.model_copy(update={'days':40,'seed':100,'repetitions':30})
    async def valid(*args):
        return {'summary':'Draft','assumptions':[],'config':edited.model_dump()}, {'model':'test'}
    monkeypatch.setattr(ai, 'completion', valid)
    result = asyncio.run(ai.draft('a test description', original))
    assert result['config']['days'] == original.days
    assert result['config']['seed'] == original.seed
    assert result['config']['repetitions'] == original.repetitions
