import pytest
from fastapi.testclient import TestClient
from app.server import create_app
from test_assessment import plan


def test_public_app_serves_website_and_assessment_api_only(tmp_path):
    site = tmp_path / 'dist'
    site.mkdir()
    (site / 'index.html').write_text('<h1>Sway assessment</h1>', encoding='utf-8')
    app = create_app(site, tmp_path / 'quota.db')
    client = TestClient(app)
    assert 'Sway assessment' in client.get('/').text
    assert client.get('/api/health').json()['status'] == 'ok'
    result = client.post('/api/assessment/calculate', json=plan().model_dump())
    assert result.status_code == 200
    assert result.json()['result']['saved_hours'] == pytest.approx(53)
    for path in ['/api/experiments', '/api/decisions/cases', '/docs', '/.env', '/backend/app/server.py']:
        assert client.get(path).status_code == 404


def test_public_quota_prevents_model_call_after_limit(tmp_path, monkeypatch):
    monkeypatch.setenv('GROQ_DAILY_CALL_LIMIT', '0')
    client = TestClient(create_app(tmp_path / 'no-assets', tmp_path / 'quota.db'))
    response = client.post('/api/assessment/analyze', json={'current_process':'A team processes two hundred requests each day.', 'ai_change':'AI drafts the responses for people to check.'})
    assert response.status_code == 429
