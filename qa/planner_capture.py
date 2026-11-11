"""Local QA wrapper: record real planner HTTP requests without changing app code.

Only synthetic QA traffic on localhost should be sent to this harness.
Run uvicorn qa.planner_capture:app with DATABASE_PATH/WEB_DIST_DIR configured.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from backend.app.main import app as real_app


async def app(scope, receive, send):
    path = scope.get('path', '')
    if (scope['type'] != 'http' or scope.get('method') != 'POST'
            or not path.startswith('/api/datasets/')
            or not (path.endswith('/plans') or path.endswith('/plans/preview'))):
        return await real_app(scope, receive, send)
    request_chunks, response_chunks = [], []
    status = None

    async def capture_receive():
        message = await receive()
        if message['type'] == 'http.request':
            request_chunks.append(message.get('body', b''))
        return message

    async def capture_send(message):
        nonlocal status
        if message['type'] == 'http.response.start':
            status = message['status']
        elif message['type'] == 'http.response.body':
            response_chunks.append(message.get('body', b''))
        await send(message)

    try:
        await real_app(scope, capture_receive, capture_send)
    finally:
        def decode(chunks):
            try:
                return json.loads(b''.join(chunks))
            except (ValueError, UnicodeError):
                return None
        record = {'time_utc': datetime.now(timezone.utc).isoformat(), 'method': 'POST',
                  'path': path, 'request': decode(request_chunks), 'status': status,
                  'response': decode(response_chunks)}
        trace = Path(os.environ.get('QA_TRACE_PATH', 'data/planner-http.jsonl'))
        trace.parent.mkdir(parents=True, exist_ok=True)
        with trace.open('a', encoding='utf-8') as output:
            output.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')
