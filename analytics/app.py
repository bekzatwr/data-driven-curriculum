"""Standalone synthetic demo and factory for the backend branch after integration."""
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from .api import router
from .common import AnalyticsError
from .demo import DATASET_ID, DemoStore


def register_analytics_errors(app):
    @app.exception_handler(AnalyticsError)
    async def analytics_error(request: Request, exc: AnalyticsError):
        details = getattr(exc, 'details', [])
        return JSONResponse(status_code=422, content={'code': exc.code, 'message': str(exc),
                                                     'details': details, 'total_errors': len(details)})


def create_demo_app():
    app = FastAPI(title='Аналитика Тони — искусственные данные', version='1.0.0')
    app.state.store = DemoStore()
    app.include_router(router)
    register_analytics_errors(app)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={
            'code': f'HTTP_{exc.status_code}', 'message': str(exc.detail), 'details': [], 'total_errors': 0})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        details = [{'field': '.'.join(map(str, e['loc'])), 'reason': e['msg']} for e in exc.errors()]
        return JSONResponse(status_code=422, content={'code': 'INVALID_REQUEST',
                            'message': 'Проверьте параметры запроса', 'details': details, 'total_errors': len(details)})

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'mode': 'isolated_synthetic_analytics_demo'}

    @app.post('/api/datasets/demo')
    def demo():
        return {'dataset_id': DATASET_ID, 'dataset': app.state.store.get_dataset(DATASET_ID)}

    @app.get('/api/datasets/{dataset_id}/filters')
    def filters(dataset_id: str):
        store = app.state.store
        records = store.load_results(dataset_id)
        return {'dataset_id': dataset_id,
                'classes': [{'id': c, 'school_id': 'DEMO-SCHOOL', 'student_count': 30} for c in ('7A', '7B', '7C', '7D')],
                'textbooks': [{'id': b, 'label': b} for b in ('Учебник A', 'Учебник B')],
                'topics': store.get_topics(dataset_id),
                'test_versions': [{'topic_id': t, 'test_version': v, 'max_score': m}
                                  for t, v, m in sorted({(r['topic_id'], r['test_version'], r['max_score']) for r in records})]}

    return app


def create_integrated_app(settings=None):
    # Backend is intentionally imported only here; main may not yet contain it.
    from backend.app.main import create_app
    app = create_app(settings=settings, routers=(router,))
    register_analytics_errors(app)
    return app
