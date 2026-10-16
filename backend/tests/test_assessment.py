import asyncio
import pytest
from pydantic import ValidationError
from backend.app import assessment, ai


def plan(**changes):
    data = dict(name='Support drafting', summary='Estimate recurring human effort for AI-drafted support responses.',
                weekly_volume=1000, adoption_percent=80,
                tasks=[dict(name='Draft response', current_minutes=10, remaining_minutes=2, explanation='AI drafts; staff still edit.'),
                       dict(name='Account checks', current_minutes=5, remaining_minutes=5, explanation='Checks remain human work.')],
                review_minutes=3, correction_percent=20, correction_minutes=4, weekly_overhead_hours=3, setup_hours=40,
                assumptions=['Times are scenario inputs.'], questions=[], risks=['Review time could increase.'],
                pilot_steps=['Measure baseline time.', 'Measure review and rework in a pilot.'])
    return assessment.WorkloadPlan.model_validate({**data, **changes})


def test_equal_demand_partial_adoption_includes_all_added_work():
    result = assessment.calculate(plan())
    assert result['current_hours'] == 250
    assert result['after_hours'] == pytest.approx(197)
    assert result['saved_hours'] == pytest.approx(53)
    assert result['verdict'] == 'decrease'
    assert sum(result['breakdown'].values()) == pytest.approx(result['after_hours'])
    assert result['first_week_hours'] == pytest.approx(237)
    assert result['setup_payback_weeks'] == pytest.approx(40 / 53)


def test_review_can_reverse_savings_and_sensitivity_shows_it():
    result = assessment.calculate(plan(review_minutes=7))
    assert result['saved_hours'] == pytest.approx(-1 / 3)
    assert result['verdict'] == 'increase'
    assert result['setup_payback_weeks'] is None
    assert result['scenarios'][0]['saved_hours'] > 0
    assert result['scenarios'][2]['saved_hours'] < 0


def test_break_even_review_matches_calculated_zero_savings():
    threshold = assessment.calculate(plan())['max_review_minutes_to_break_even']
    result = assessment.calculate(plan(review_minutes=threshold))
    assert result['saved_hours'] == pytest.approx(0)
    assert result['verdict'] == 'unchanged'


def test_no_ai_adoption_still_counts_fixed_overhead():
    result = assessment.calculate(plan(adoption_percent=0))
    assert result['after_hours'] == 253
    assert result['max_review_minutes_to_break_even'] is None
    assert result['breakdown']['checking'] == 0


def test_setup_is_not_subtracted_from_every_week():
    low = assessment.calculate(plan(setup_hours=0))
    high = assessment.calculate(plan(setup_hours=1000))
    assert low['after_hours'] == high['after_hours']
    assert high['first_week_hours'] - low['first_week_hours'] == 1000


@pytest.mark.parametrize('changes', [dict(adoption_percent=101), dict(correction_percent=-1), dict(weekly_volume=0),
                                   dict(review_minutes=float('nan')), dict(weekly_overhead_hours=float('inf')), dict(tasks=[])])
def test_invalid_workload_inputs_are_rejected(changes):
    with pytest.raises(ValidationError):
        plan(**changes)


def test_zero_baseline_cannot_produce_misleading_percentage():
    p = plan()
    for task in p.tasks:
        task.current_minutes = 0
    with pytest.raises(ValueError):
        assessment.calculate(p)


def test_model_receives_both_real_descriptions_and_validates_output(monkeypatch):
    request = assessment.Description(current_process='A team processes two hundred requests each day.', ai_change='AI drafts the responses; people check and correct them.')
    async def fake(system, data, schema):
        assert data == request.model_dump()
        assert 'HUMAN WORKLOAD' in system
        assert schema['additionalProperties'] is False
        return plan().model_dump(), {'model': 'test', 'tokens': 100}
    monkeypatch.setattr(ai, 'completion', fake)
    result = asyncio.run(assessment.analyze(request))
    assert result['plan']['weekly_volume'] == 1000
    assert 'result' not in result  # User reviews assumptions before calculation.


def test_invalid_model_output_fails_without_fabricated_result(monkeypatch):
    async def fake(*args):
        return {'claim': 'AI saves half your time'}, {}
    monkeypatch.setattr(ai, 'completion', fake)
    with pytest.raises(ai.AIUnavailable):
        asyncio.run(assessment.analyze(assessment.Description(current_process='A team processes two hundred requests each day.', ai_change='AI drafts responses for people to review.')))


def test_assessment_api_calculates_without_provider_and_rejects_bad_inputs(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from app.storage import LocalStore
    monkeypatch.setattr(main, 'store', LocalStore(tmp_path / 'assessment.db'))
    client = TestClient(main.app)
    response = client.post('/api/assessment/calculate', json=plan().model_dump())
    assert response.status_code == 200
    assert response.json()['result']['after_hours'] == pytest.approx(197)
    assert client.post('/api/assessment/calculate', json={}).status_code == 422
    assert client.post('/api/assessment/analyze', json={'current_process': 'short', 'ai_change': 'short'}).status_code == 422


def test_analysis_api_preserves_provider_failure_and_enforces_quota(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from app.storage import LocalStore
    monkeypatch.setattr(main, 'store', LocalStore(tmp_path / 'assessment.db'))
    monkeypatch.setenv('GROQ_DAILY_CALL_LIMIT', '1')
    async def unavailable(request):
        raise main.ai.AIUnavailable('Provider unavailable; no assessment generated.')
    monkeypatch.setattr(main.assessment, 'analyze', unavailable)
    client = TestClient(main.app)
    payload = {'current_process': 'A team processes two hundred requests each day.', 'ai_change': 'AI drafts responses for people to review.'}
    response = client.post('/api/assessment/analyze', json=payload)
    assert response.status_code == 503
    assert 'no assessment' in response.json()['detail']
    assert client.post('/api/assessment/analyze', json=payload).status_code == 429
