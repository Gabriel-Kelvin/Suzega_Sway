"""Local repository boundary. Replace this adapter when a remote DB is requested."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4


class LocalStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS ai_usage (id INTEGER PRIMARY KEY, day TEXT NOT NULL, kind TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, result):
        result = {**result, 'id': uuid4().hex, 'created_at': datetime.now(timezone.utc).isoformat()}
        with self.connect() as db:
            db.execute('INSERT INTO experiments VALUES (?,?,?,?)', (result['id'], result['config']['name'], result['created_at'], json.dumps(result)))
        return result

    def list(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT id,name,created_at FROM experiments ORDER BY created_at DESC LIMIT 50')]

    def get(self, id):
        with self.connect() as db:
            row = db.execute('SELECT payload FROM experiments WHERE id=?', (id,)).fetchone()
            return json.loads(row['payload']) if row else None

    def reserve_ai_call(self, limit, kind):
        day = datetime.now(timezone.utc).date().isoformat()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            count = db.execute('SELECT count(*) FROM ai_usage WHERE day=?', (day,)).fetchone()[0]
            if count >= limit:
                return False
            db.execute('INSERT INTO ai_usage(day,kind) VALUES (?,?)', (day, kind))
            return True
