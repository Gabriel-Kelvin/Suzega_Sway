"""Public deployment: one website and only the workload-assessment API."""
import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from .storage import LocalStore
from .workload_api import router

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')


def create_app(static_dir=None, database_path=None):
    app = FastAPI(title='Sway AI Workload Assessment', version='1.0.0', docs_url=None, redoc_url=None, openapi_url=None)
    quota = LocalStore(Path(database_path or os.getenv('DATABASE_PATH', '/tmp/sway/quota.db')))

    def reserve(kind):
        if not quota.reserve_ai_call(int(os.getenv('GROQ_DAILY_CALL_LIMIT', '30')), kind):
            raise HTTPException(429, 'The demo’s daily AI request limit was reached. You can still recalculate and download an existing assessment.')

    app.state.reserve = reserve
    app.include_router(router)

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'app': 'Sway AI Workload Assessment', 'version': '1.0.0', 'ai_configured': bool(os.getenv('GROQ_API_KEY'))}

    assets = Path(static_dir) if static_dir is not None else ROOT / 'frontend' / 'dist'
    if assets.is_dir():
        app.mount('/', StaticFiles(directory=assets, html=True), name='website')
    return app


app = create_app()
