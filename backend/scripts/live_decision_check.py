"""Optional live smoke checks. Creates local cases and uses real Groq requests.

Run with the API running: python backend/scripts/live_decision_check.py
These few examples are smoke tests, not an accuracy benchmark.
"""
import argparse
import json
from pathlib import Path
import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', nargs='+', default=['missing', 'conflict', 'injection'])
    args = parser.parse_args()
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=90) as client:
        setup = client.get('/api/decisions/setup').raise_for_status().json()
        report = []
        for sample in setup['samples']:
            if sample['id'] not in args.samples:
                continue
            payload = {k: sample[k] for k in ('title', 'text', 'documents')}
            payload['title'] = 'Live check: ' + payload['title']
            payload['workflow'] = setup['workflow']
            case = client.post('/api/decisions/cases', json=payload).raise_for_status().json()
            response = client.post(f"/api/decisions/cases/{case['id']}/run")
            if response.status_code != 200:
                item = {'sample': sample['id'], 'case_id': case['id'], 'http_status': response.status_code, 'error': response.json().get('detail')}
            else:
                result = response.json()
                decision = result['decision']
                expected = {
                    'outage': decision['action'] == 'route' and decision['team'] == 'Technical Support' and decision['priority'] == 'high',
                    'missing': decision['action'] == 'request_info' and bool(decision['missing_information']),
                    'resolved': decision['action'] == 'resolve' and result['status'] == 'review_required',
                    'conflict': decision['action'] == 'escalate' and result['status'] == 'review_required',
                    'injection': decision['action'] in ('route', 'escalate') and decision['team'] in setup['workflow']['teams'] and result['local_state']['status'] != 'resolved',
                }[sample['id']]
                item = {'sample': sample['id'], 'case_id': case['id'], 'status': result['status'], 'action': decision['action'],
                        'team': decision['team'], 'priority': decision['priority'], 'source_checks_passed': result['validation']['passed'],
                        'expected_behavior_observed': expected, 'meta': result['meta']}
            report.append(item)
            print(json.dumps(item, ensure_ascii=True), flush=True)
        output = Path(__file__).resolve().parents[2] / 'work' / 'live-decision-check.json'
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
