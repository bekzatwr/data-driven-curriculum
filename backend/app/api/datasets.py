from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from ..db import Store
from ..demo import demo_files
from ..errors import ApiError
from ..schemas import Dataset, DatasetList, ErrorResponse, Filters, ImportResponse, RecordsPage, Topic
from ..validation import RESULT_FIELDS, TOPIC_FIELDS, validate_upload

router = APIRouter(prefix="/api", tags=["Datasets"], responses={
    code: {"model": ErrorResponse} for code in (400, 403, 404, 413, 422)
})


def get_store(request: Request) -> Store:
    return request.app.state.store


StoreDep = Annotated[Store, Depends(get_store)]


def import_response(upload, dry_run, dataset=None, created=False):
    body = ImportResponse(
        dry_run=dry_run, created=created, dataset=dataset,
        dataset_id=dataset["id"] if dataset else None, metadata=upload.metadata,
        counts=upload.counts, warnings=upload.warnings,
        preview={"results": upload.results[:10], "curriculum": upload.topics[:10]},
    )
    return JSONResponse(status_code=201 if created else 200, content=jsonable_encoder(body))


@router.post("/datasets/import", response_model=ImportResponse, responses={201: {"model": ImportResponse}})
async def import_dataset(
    request: Request, store: StoreDep,
    results_file: Annotated[UploadFile, File(description="UTF-8 results.csv")],
    curriculum_file: Annotated[UploadFile, File(description="UTF-8 curriculum.csv")],
    metadata: Annotated[str, Form(description="JSON: name, subject, grade, period_start, period_end")],
    dry_run: bool = True,
    error_format: Literal["json", "csv"] = "json",
):
    settings = request.app.state.settings
    try:
        if settings.read_only_demo:
            raise ApiError(403, "READ_ONLY_DEMO", "Импорт доступен только в локальном или закрытом режиме.")
        payloads = []
        size = 0
        for file in (results_file, curriculum_file):
            if not file.filename or not file.filename.lower().endswith(".csv"):
                raise ApiError(422, "INVALID_FILE_TYPE", "Загрузите два файла с расширением .csv.")
            chunks = []
            while chunk := await file.read(64 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise ApiError(413, "UPLOAD_TOO_LARGE", "Суммарный размер CSV превышает 10 МБ.")
                chunks.append(chunk)
            payloads.append(b"".join(chunks))
        upload = await run_in_threadpool(validate_upload, *payloads, metadata, settings)
        if dry_run:
            return import_response(upload, True)
        dataset, created = await run_in_threadpool(store.save_upload, upload)
        return import_response(upload, False, dataset, created)
    except ApiError as exc:
        return exc.response(as_csv=error_format == "csv")
    finally:
        await results_file.close()
        await curriculum_file.close()


@router.post("/datasets/demo", response_model=ImportResponse, responses={201: {"model": ImportResponse}})
def create_demo(request: Request, store: StoreDep):
    upload = validate_upload(*demo_files(), request.app.state.settings, source_type="demo")
    dataset, created = store.save_upload(upload)
    return import_response(upload, False, dataset, created)


@router.get("/datasets", response_model=DatasetList)
def list_datasets(store: StoreDep, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return store.list_datasets(limit, offset)


@router.get("/datasets/{dataset_id}", response_model=Dataset)
def get_dataset(dataset_id: str, store: StoreDep):
    return store.get_dataset(dataset_id)


@router.get("/datasets/{dataset_id}/filters", response_model=Filters)
def get_filters(dataset_id: str, store: StoreDep):
    return store.get_filters(dataset_id)


@router.get("/datasets/{dataset_id}/curriculum", response_model=list[Topic])
def get_curriculum(dataset_id: str, store: StoreDep):
    return store.get_topics(dataset_id)


@router.get("/datasets/{dataset_id}/results", response_model=RecordsPage)
def get_results(
    dataset_id: str, store: StoreDep,
    class_ids: Annotated[list[str] | None, Query(max_length=100)] = None,
    textbook_ids: Annotated[list[str] | None, Query(max_length=100)] = None,
    topic_id: str | None = None, stage: Literal["pre", "post"] | None = None,
    test_version: str | None = None, limit: int = Query(1000, ge=1, le=1000), offset: int = Query(0, ge=0),
):
    return store.list_results(dataset_id, class_ids=class_ids, textbook_ids=textbook_ids,
                              topic_id=topic_id, stage=stage, test_version=test_version, limit=limit, offset=offset)


@router.get("/templates/{name}.csv", tags=["Templates"])
def template(name: Literal["results", "curriculum"]):
    fields = RESULT_FIELDS if name == "results" else TOPIC_FIELDS
    return Response((",".join(fields) + "\n").encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})
