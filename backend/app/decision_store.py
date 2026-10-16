"""Transactional local case state and a hash-linked audit trail."""
import json
from datetime import datetime, timezone
from uuid import uuid4
from .decisions import canonical_hash, execute_local, validate_decision


def now():
    return datetime.now(timezone.utc).isoformat()


class CaseConflict(Exception):
    pass


class DecisionStore:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS decision_cases (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS decision_events (case_id TEXT NOT NULL, seq INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(case_id,seq));
                CREATE TABLE IF NOT EXISTS workspace_settings (name TEXT PRIMARY KEY, payload TEXT NOT NULL);
            ''')

    def settings(self):
        with self.store.connect() as db:
            row = db.execute('SELECT payload FROM workspace_settings WHERE name=?', ('decision_workflow',)).fetchone()
            return json.loads(row['payload']) if row else None

    def save_settings(self, value):
        with self.store.connect() as db:
            db.execute('INSERT INTO workspace_settings VALUES (?,?) ON CONFLICT(name) DO UPDATE SET payload=excluded.payload', ('decision_workflow', json.dumps(value)))
        return value

    def _event(self, db, case, kind, data):
        row = db.execute('SELECT payload FROM decision_events WHERE case_id=? ORDER BY seq DESC LIMIT 1', (case['id'],)).fetchone()
        previous = json.loads(row['payload']) if row else None
        event = {'case_id': case['id'], 'seq': previous['seq'] + 1 if previous else 1, 'at': now(), 'kind': kind,
                 'data': data, 'previous_hash': previous['hash'] if previous else '0' * 64}
        event['hash'] = canonical_hash(event)
        db.execute('INSERT INTO decision_events VALUES (?,?,?)', (case['id'], event['seq'], json.dumps(event)))

    def _write(self, db, case):
        case['updated_at'] = now()
        db.execute('UPDATE decision_cases SET payload=? WHERE id=?', (json.dumps(case), case['id']))

    def _read(self, db, id):
        row = db.execute('SELECT payload FROM decision_cases WHERE id=?', (id,)).fetchone()
        if row is None:
            raise KeyError(id)
        return json.loads(row['payload'])

    def create(self, data):
        case = {**data, 'id': uuid4().hex, 'created_at': now(), 'updated_at': now(), 'status': 'ready',
                'input_hash': canonical_hash(data), 'decision': None, 'validation': None, 'meta': None, 'error': None,
                'local_state': {'status': 'new', 'team': None, 'priority': None, 'response_draft': ''}}
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO decision_cases VALUES (?,?,?)', (case['id'], case['created_at'], json.dumps(case)))
            self._event(db, case, 'case_created', {'input_hash': case['input_hash'], 'workflow': data['workflow']['name']})
        return self.get(case['id'])

    def get(self, id):
        with self.store.connect() as db:
            case = self._read(db, id)
            case['events'] = [json.loads(r['payload']) for r in db.execute('SELECT payload FROM decision_events WHERE case_id=? ORDER BY seq', (id,))]
        return case

    def list(self):
        with self.store.connect() as db:
            items = [json.loads(r['payload']) for r in db.execute('SELECT payload FROM decision_cases ORDER BY created_at DESC LIMIT 100')]
        return [{key: c[key] for key in ('id', 'title', 'created_at', 'status', 'local_state', 'meta')} for c in items]

    def begin(self, id):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            case = self._read(db, id)
            if case['status'] not in ('ready', 'failed'):
                raise CaseConflict('This case has already been processed or is running. Create a new case to test different inputs.')
            case.update(status='processing', error=None)
            self._event(db, case, 'model_requested', {'input_hash': case['input_hash']})
            self._write(db, case)
        return case

    def finish(self, id, decision, meta):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            case = self._read(db, id)
            if case['status'] != 'processing':
                raise CaseConflict('The case is no longer waiting for a model decision.')
            validation = validate_decision(case, decision)
            case.update(decision=decision, validation=validation, meta=meta)
            self._event(db, case, 'model_decided', {'decision': decision, 'meta': meta})
            self._event(db, case, 'python_validated', validation)
            if not validation['passed']:
                case['status'] = 'blocked'
                self._event(db, case, 'action_blocked', {'reason': 'A deterministic validation check failed. No action executed.'})
            elif validation['review_reasons']:
                case['status'] = 'review_required'
                self._event(db, case, 'review_requested', {'reasons': validation['review_reasons']})
            else:
                action = execute_local(case, decision, 'ai_policy_authorized')
                self._event(db, case, 'action_executed', action)
            self._write(db, case)
        return self.get(id)

    def fail(self, id, error):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            case = self._read(db, id)
            if case['status'] == 'processing':
                case.update(status='failed', error=error)
                self._event(db, case, 'run_failed', {'error': error, 'action_executed': False})
                self._write(db, case)
        return self.get(id)

    def recover(self):
        # On this single-process local server, interrupted runs can safely be retried.
        with self.store.connect() as db:
            cases = [json.loads(r['payload']) for r in db.execute('SELECT payload FROM decision_cases')]
        for case in cases:
            if case['status'] == 'processing':
                self.fail(case['id'], 'The server restarted before the decision finished. No action was executed. Retry this case.')

    def review(self, id, verdict, reason):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            case = self._read(db, id)
            if case['status'] != 'review_required':
                raise CaseConflict('Only a case awaiting review can be approved or rejected.')
            validation = validate_decision(case, case['decision'])
            if not validation['passed']:
                raise CaseConflict('Validation failed. Approval cannot bypass evidence or action checks.')
            self._event(db, case, 'human_reviewed', {'verdict': verdict, 'reason': reason, 'actor': 'local_operator'})
            if verdict == 'approve':
                self._event(db, case, 'action_executed', execute_local(case, case['decision'], 'local_operator'))
            else:
                case['status'] = 'rejected'
            self._write(db, case)
        return self.get(id)

    def audit(self, id):
        case = self.get(id)
        previous = '0' * 64
        valid = True
        for index, event in enumerate(case['events'], 1):
            data = {k: v for k, v in event.items() if k != 'hash'}
            valid = valid and event['seq'] == index and event['previous_hash'] == previous and event['hash'] == canonical_hash(data)
            previous = event['hash']
        original = {key: case[key] for key in ('title', 'text', 'documents', 'workflow')}
        valid = valid and canonical_hash(original) == case['input_hash']
        return {'valid': valid, 'events': len(case['events']), 'last_hash': previous,
                'scope': 'Checks source snapshot hash and audit chain integrity. Does not certify decision correctness or protect against a database owner rewriting the entire chain.'}
