import csv
import io
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError
from .models import PlanRequest, SaveRequest
from .rules import PlanError
from .service import preview, save_plan
from .contracts import PlanPreview, SavedPlan, PlanErrorResponse

router = APIRouter(prefix='/api', tags=['Plans'], responses={
    status: {'model': PlanErrorResponse} for status in (404, 422, 503)
})


def error(message, status=422):
    return JSONResponse(status_code=status, content={'code': 'PLAN_NOT_FOUND' if status == 404 else 'INVALID_PLAN', 'message': message, 'details': [], 'total_errors': 0})


@router.post('/datasets/{dataset_id}/plans/preview', response_model=PlanPreview, response_model_exclude_unset=True)
def preview_route(dataset_id: str, payload: PlanRequest, request: Request):
    try:
        return preview(request.app.state.store, dataset_id, payload)
    except (PlanError, ValidationError) as exc:
        return error(str(exc))


@router.post('/datasets/{dataset_id}/plans', status_code=201, response_model=SavedPlan, response_model_exclude_unset=True,
             responses={403: {'model': PlanErrorResponse, 'description': 'Public read-only demo: saving is disabled'}})
def save_route(dataset_id: str, payload: SaveRequest, request: Request):
    try:
        return save_plan(request.app.state.store, request.app.state.plan_snapshots, dataset_id, payload,
                         response_factory=lambda snapshot: JSONResponse(status_code=201, content=snapshot))
    except (PlanError, ValidationError) as exc:
        return error(str(exc))


def visible_plan(request, plan_id):
    plan = request.app.state.plan_snapshots.get(plan_id)
    if plan and getattr(request.app.state.store, 'demo_only', False) and not plan['is_demo']:
        return None
    return plan


@router.get('/plans/{plan_id}', response_model=SavedPlan, response_model_exclude_unset=True)
def get_route(plan_id: str, request: Request):
    return visible_plan(request, plan_id) or error('План не найден', 404)


def export_csv(plan):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    columns = ['topic_id', 'topic_name', 'mean_post_pct', 'n_post', 'current_hours', 'min_hours', 'max_hours', 'importance', 'is_locked', 'recommended_hours', 'proposed_hours', 'delta', 'manually_modified', 'reason']
    metadata = ['plan_id', 'dataset_id', 'class_id', 'created_at', 'algorithm_version', 'is_demo']
    writer.writerow(metadata + columns)
    def safe(value):
        if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
            return "'" + value
        return value
    for item in plan['items']:
        writer.writerow([safe(plan[k]) for k in metadata] + [safe(item.get(k)) for k in columns])
    return stream.getvalue().encode('utf-8-sig')


@router.get('/plans/{plan_id}/export.csv', response_class=Response,
            responses={200: {'content': {'text/csv': {'schema': {'type': 'string'}}},
                             'description': 'Saved snapshot as UTF-8 CSV with BOM'}})
def export_route(plan_id: str, request: Request):
    plan = visible_plan(request, plan_id)
    if not plan:
        return error('План не найден', 404)
    return Response(export_csv(plan), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': 'attachment; filename="curriculum-plan.csv"'})
