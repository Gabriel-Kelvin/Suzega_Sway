import pytest
from pydantic import ValidationError
from app.models import ExperimentConfig
from app.simulation import simulate, compare, human_service, shift_length, workday


@pytest.fixture
def config():
    return ExperimentConfig(days=10, daily_cases=20, repetitions=3)


def test_friday_service_resumes_monday(config):
    friday = 4 * 1440
    start, end, segments = human_service(friday + 350, 30, config)
    assert start == friday + 350
    assert segments == [(friday + 350, friday + 360), (7 * 1440, 7 * 1440 + 20)]
    assert end == 7 * 1440 + 20


@pytest.mark.parametrize('strategy', ['current', 'automated', 'augmented'])
@pytest.mark.parametrize('disruption', ['none', 'surge', 'outage', 'absence', 'exceptions'])
def test_conservation_and_human_boundaries(config, strategy, disruption):
    config.disruption = disruption
    result = simulate(config, strategy, 42, True)
    m = result['metrics']
    assert m['arrivals'] == m['completed'] + m['backlog']
    assert m['arrivals'] == 240 if disruption == 'surge' else m['arrivals'] == 200
    assert 0 <= m['reviewer_utilization'] <= 100.00001
    assert 0 <= m['sla_percent'] <= 100
    assert m['mean_hours'] > 0
    for record in result['sample_cases']:
        if config.stages[record['stage']].requires_human:
            assert record['resource'] == 'human'
        if record['resource'] == 'human':
            for start, end in record['segments']:
                day = int(start // 1440)
                assert day % 7 < 5
                assert end <= day * 1440 + shift_length(day, config) + .01
    for frame in result['frames']:
        assert all(s['waiting'] >= 0 and s['active'] >= 0 for s in frame['stages'])


def test_reproducible_paired_comparison(config):
    assert compare(config) == compare(config)


def test_no_assistance_means_identical_automated_arrangements(config):
    config.assist_multiplier = 1
    assert simulate(config, 'automated', 42, True) == simulate(config, 'augmented', 42, True)


def test_ai_speed_does_not_change_human_baseline(config):
    baseline = simulate(config, 'current', 42)
    config.ai_speed = 10
    assert simulate(config, 'current', 42) == baseline


def test_outage_does_not_drop_work(config):
    config.daily_cases = 80
    normal = simulate(config, 'automated', 42)
    config.disruption = 'outage'
    outage = simulate(config, 'automated', 42)
    assert normal['metrics']['arrivals'] == outage['metrics']['arrivals']
    assert normal['metrics']['human_hours'] == outage['metrics']['human_hours']
    assert outage['metrics']['mean_hours'] >= normal['metrics']['mean_hours']


def test_human_authority_and_unique_ids_are_required(config):
    data = config.model_dump()
    for s in data['stages']:
        s['requires_human'] = False
    with pytest.raises(ValidationError):
        ExperimentConfig.model_validate(data)
    data = config.model_dump()
    data['stages'][1]['id'] = data['stages'][0]['id']
    with pytest.raises(ValidationError):
        ExperimentConfig.model_validate(data)
