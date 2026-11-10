"""Standalone demo and explicit integration factory for Bekzat's backend."""
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from .api import router
from .demo import DemoStore
from .storage import SnapshotStore


def create_demo_app(database_path=None):
    app = FastAPI(title='Планировщик Айданы — искусственные данные', version='1.0.0')
    app.state.store = DemoStore()
    app.state.plan_snapshots = SnapshotStore(database_path or os.getenv('PLAN_DATABASE_PATH', 'data/aidana-plans.sqlite3'))
    app.include_router(router)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={'code': f'HTTP_{exc.status_code}', 'message': str(exc.detail), 'details': []})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={'code': 'INVALID_REQUEST', 'message': 'Проверьте параметры запроса',
                            'details': [{'field': '.'.join(map(str, e['loc'])), 'reason': e['msg']} for e in exc.errors()]})

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'mode': 'isolated_synthetic_planner_demo'}

    @app.post('/api/datasets/demo')
    def demo():
        return {'dataset_id': 'aidana-demo', 'dataset': app.state.store.get_dataset('aidana-demo')}

    return app


def create_integrated_app():
    # Compatibility entry point: the default backend now includes the planner.
    from backend.app.main import create_app
    return create_app()
