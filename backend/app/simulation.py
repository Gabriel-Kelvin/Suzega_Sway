"""Seeded discrete-event simulation. No model calls or business outcome shortcuts.

Time is elapsed minutes from Monday 09:00. Human capacity follows weekday
calendars; Friday learning reduces available service minutes. A service task
pauses at shift end and resumes next working day. Each stage has a dedicated
human pool; AI stages have two concurrent slots. No staff is removed by automation.
"""
import hashlib
import heapq
import random
import statistics
from .models import ExperimentConfig

VERSION = 'sway-des-1.0.0'
STRATEGIES = [
    {'id': 'current', 'name': 'Today’s process', 'description': 'People handle every step.'},
    {'id': 'automated', 'name': 'Accelerate with AI', 'description': 'Automate routine steps. Keep final review unchanged.'},
    {'id': 'augmented', 'name': 'Amplify people', 'description': 'Automate routine steps and assist human reviewers.'},
]


def workday(index: int) -> int:
    return index // 5 * 7 + index % 5


def shift_length(day: int, config: ExperimentConfig) -> float:
    if day % 7 >= 5:
        return 0
    return config.work_hours * 60 - (config.learning_hours * 60 if day % 7 == 4 else 0)


def next_work_time(t: float, config: ExperimentConfig) -> float:
    while True:
        day = int(t // 1440)
        end = day * 1440 + shift_length(day, config)
        if t < end - 1e-8:
            return t
        t = (day + 1) * 1440.0


def human_service(t: float, duration: float, config: ExperimentConfig):
    segments = []
    t = next_work_time(t, config)
    start = t
    while duration > 1e-8:
        day = int(t // 1440)
        usable = min(duration, day * 1440 + shift_length(day, config) - t)
        if usable > 0:
            segments.append((t, t + usable))
        duration -= usable
        t += usable
        if duration > 1e-8:
            t = next_work_time(t, config)
    return start, t, segments


def rng_for(seed, case, stage, kind):
    raw = hashlib.sha256(f'{seed}:{case}:{stage}:{kind}'.encode()).digest()
    return random.Random(int.from_bytes(raw[:8], 'big'))


def percentile(values, q):
    if not values:
        return 0.0
    xs = sorted(values)
    k = (len(xs) - 1) * q
    low = int(k)
    return xs[low] + (xs[min(low + 1, len(xs) - 1)] - xs[low]) * (k - low)


def simulate(config: ExperimentConfig, strategy: str, seed: int, include_trace=False):
    horizon = workday(config.days - 1) * 1440 + config.work_hours * 60
    events = []
    arrivals = {}
    arrival_rng = random.Random(seed)
    for i in range(config.days):
        n = config.daily_cases * (2 if config.disruption == 'surge' and 8 <= i < 11 else 1)
        for _ in range(n):
            case = len(arrivals)
            at = workday(i) * 1440 + arrival_rng.random() * config.work_hours * 60
            arrivals[case] = at
            heapq.heappush(events, (at, case, 0, False))

    pools = []
    capacity = []
    for stage in config.stages:
        workers = max(1, stage.workers - (1 if config.disruption == 'absence' and stage.requires_human else 0))
        pools.append({'human': [0.] * workers, 'ai': [0., 0.]})
        capacity.append(workers * sum(shift_length(workday(i), config) for i in range(config.days)))
    records, completions = [], {}
    human_busy = [0.] * len(config.stages)
    human_total = [0.] * len(config.stages)
    waits = [[] for _ in config.stages]
    exception_count = 0
    ai_count = 0
    outage_start = workday(8) * 1440 + 120
    outage_end = outage_start + 1440

    while events:
        at, case, idx, escalated = heapq.heappop(events)
        if idx == len(config.stages):
            completions[case] = at
            continue
        stage = config.stages[idx]
        human = strategy == 'current' or stage.requires_human or escalated
        resource = 'human' if human else 'ai'
        slots = pools[idx][resource]
        free = heapq.heappop(slots)
        requested_start = max(at, free)
        complex_case = rng_for(seed, case, 0, 'complex').random() < config.complex_share
        multiplier = 1.8 if complex_case else 1
        variation = rng_for(seed, case, idx, resource).lognormvariate(-.5 * .35**2, .35)
        if human:
            duration = stage.human_minutes * multiplier * variation
            if strategy == 'augmented' and stage.requires_human:
                duration *= config.assist_multiplier
            start, end, segments = human_service(requested_start, duration, config)
            human_total[idx] += duration
            human_busy[idx] += sum(max(0, min(b, horizon) - a) for a, b in segments if a < horizon)
        else:
            duration = stage.ai_minutes / config.ai_speed * variation * (1.2 if complex_case else 1)
            start = requested_start
            if config.disruption == 'outage' and outage_start <= start < outage_end:
                start = outage_end
            end = start + duration
            segments = [(start, end)]
            if config.disruption == 'outage' and start < outage_start < end:
                end += outage_end - outage_start
                segments = [(start, outage_start), (outage_end, end)]
            ai_count += 1
        heapq.heappush(slots, end)
        waits[idx].append(max(0, start - at))
        records.append({'case': case, 'stage': idx, 'resource': resource, 'arrival': at, 'start': start, 'end': end, 'exception': escalated, 'segments': segments})
        exception_rate = min(.95, config.exception_rate * (2 if config.disruption == 'exceptions' else 1))
        # Shared random draws keep comparisons paired. Exception probability is
        # an explicit assumption, never inferred from a model's self-confidence.
        needs_exception = not human and rng_for(seed, case, idx, 'exception').random() < exception_rate
        if needs_exception:
            exception_count += 1
            heapq.heappush(events, (end, case, idx, True))
        else:
            heapq.heappush(events, (end, case, idx + 1, False))

    total = len(arrivals)
    closed = [c for c, end in completions.items() if end <= horizon]
    elapsed = [(completions[c] - arrivals[c]) / 60 for c in arrivals]
    within_sla = sum(h <= config.sla_hours for h in elapsed)
    end_backlog = total - len(closed)
    # Follow all arrivals to closure so late cases are not dropped from latency.
    labor_hours = sum(human_total) / 60
    cost = labor_hours * config.hourly_cost + ai_count * config.ai_case_cost
    metrics = {
        'arrivals': total, 'completed': len(closed), 'backlog': end_backlog,
        'mean_hours': statistics.mean(elapsed), 'p90_hours': percentile(elapsed, .9),
        'sla_percent': 100 * within_sla / total, 'human_hours': labor_hours,
        'cost_per_case': cost / total, 'total_cost': cost,
        'exceptions': exception_count, 'reviewer_utilization': max(human_busy[i] / max(1, capacity[i]) * 100 for i, s in enumerate(config.stages) if s.requires_human),
        'clearance_days': max(0, (max(completions.values()) - horizon) / 1440),
    }
    result = {'metrics': metrics}
    if include_trace:
        snapshots = []
        starts = sorted(arrivals.values())
        ends = sorted(completions.values())
        import bisect
        for i in range(config.days):
            t = workday(i) * 1440 + config.work_hours * 60
            arrived = bisect.bisect_right(starts, t)
            done = bisect.bisect_right(ends, t)
            snapshots.append({'day': i + 1, 'time': t, 'arrived': arrived, 'completed': done, 'backlog': arrived - done})
        stages = []
        for i, stage in enumerate(config.stages):
            stages.append({'id': stage.id, 'name': stage.name, 'utilization': round(human_busy[i] / max(1, capacity[i]) * 100, 2), 'mean_wait_hours': round(statistics.mean(waits[i]) / 60, 2), 'human_hours': round(human_total[i] / 60, 2)})
        # Exact all-case state counts at a bounded set of timestamps. Frontend
        # particles are illustrative, while counters are computed from every case.
        frames = []
        grids = [[r for r in records if r['stage'] == i] for i in range(len(config.stages))]
        for d in range(config.days):
            for fraction in (.05, .25, .5, .75, .99):
                t = workday(d) * 1440 + fraction * config.work_hours * 60
                stage_counts = []
                for rs in grids:
                    stage_counts.append({
                        'waiting': sum(r['arrival'] <= t < r['start'] for r in rs),
                        'active': sum(any(a <= t < b for a, b in r['segments']) for r in rs),
                    })
                frames.append({'time': round(t, 2), 'day': d + 1, 'stages': stage_counts, 'completed': bisect.bisect_right(ends, t)})
        result.update({'daily': snapshots, 'stages': stages, 'frames': frames, 'horizon_minutes': horizon,
                       'sample_cases': [{**r, 'segments': [[round(a, 2), round(b, 2)] for a, b in r['segments']]} for r in records if r['case'] < 8]})
    return result


def compare(config: ExperimentConfig):
    results = []
    for strategy in STRATEGIES:
        runs = [simulate(config, strategy['id'], config.seed + n, n == 0) for n in range(config.repetitions)]
        metrics = {}
        for key in runs[0]['metrics']:
            values = [r['metrics'][key] for r in runs]
            metrics[key] = {'mean': round(statistics.mean(values), 3), 'low': round(percentile(values, .1), 3), 'high': round(percentile(values, .9), 3)}
        results.append({**strategy, 'metrics': metrics, **{k: v for k, v in runs[0].items() if k != 'metrics'}})
    baseline, automated, augmented = results
    get = lambda s, m: s['metrics'][m]['mean']
    slowest = max(automated['stages'], key=lambda s: s['mean_wait_hours'])
    improvement = (get(baseline, 'mean_hours') - get(augmented, 'mean_hours')) / max(.001, get(baseline, 'mean_hours')) * 100
    insight = {
        'title': f"{slowest['name']} is the longest wait after automation",
        'body': f"In the representative run, cases wait {slowest['mean_wait_hours']:.1f} elapsed hours at this stage. Across runs, assisted review changes average turnaround by {improvement:.0f}% versus today’s process. This depends on the assumed review-time reduction.",
        'improvement_percent': round(improvement, 1),
        'bottleneck_stage': slowest['id'],
    }
    return {'engine_version': VERSION, 'config': config.model_dump(), 'strategies': results, 'insight': insight,
            'methodology': {'repetitions': config.repetitions, 'seeds': list(range(config.seed, config.seed + config.repetitions)),
                'range': '10th–90th percentile across simulated runs, not a statistical confidence interval.',
                'latency': 'Elapsed calendar hours for every arriving case, followed to closure beyond the observation window.',
                'cost': 'Active human service time × hourly cost + AI executions × assumed cost. Includes backlog clearance; excludes salaries for idle time, integration and infrastructure.',
                'calendar': 'Monday–Friday; daily shifts begin at 09:00; Friday learning time reduces service capacity. Tasks pause at shift end.',
                'limitations': ['Synthetic inputs; no real client data or calibrated forecast.', 'Independent stage teams, FIFO queues, no prioritization or abandonment.', 'Two concurrent AI slots per stage. AI exceptions return to the same stage’s human team.', 'Assisted review reduces human service time by an explicit assumption; it does not establish decision accuracy.', 'No layoffs, wellbeing score, legal compliance certification or quality equivalence are modeled.']}}
