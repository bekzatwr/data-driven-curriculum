// Запуск: npm test. Регрессия: таймер снимался после заголовков, и запрос с оборванным телом
// «грузился» бесконечно. Настоящий модуль client.ts собирается esbuild (зависимость Vite)
// и работает с синтетическим локальным HTTP-сервером; сеть и браузер не нужны.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { build } = require('esbuild');

const server = http.createServer((req, res) => {
  if (req.url?.startsWith('/no-headers')) return; // не отвечает вовсе
  if (req.url?.startsWith('/partial-body')) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.write('{"status":'); // заголовки и начало JSON, дальше тишина
    return;
  }
  if (req.url?.startsWith('/slow-ok')) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.write('{"status":');
    setTimeout(() => res.end('"ok"}'), 150);
    return;
  }
  if (req.url?.startsWith('/invalid')) {
    res.writeHead(422, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ code: 'VALIDATION_ERROR', message: 'Сумма часов не совпадает', details: [] }));
    return;
  }
  res.writeHead(404).end();
});

let client: any;

before(async () => {
  await new Promise<void>((done) => server.listen(0, '127.0.0.1', done));
  const { port } = server.address() as { port: number };
  const bundle = await build({
    entryPoints: [fileURLToPath(new URL('./client.ts', import.meta.url))],
    bundle: true,
    write: false,
    platform: 'node',
    format: 'esm',
    logLevel: 'silent',
    define: { 'import.meta.env': JSON.stringify({ VITE_API_BASE_URL: `http://127.0.0.1:${port}` }) },
  });
  const code = Buffer.from(bundle.outputFiles[0].contents).toString('base64');
  client = await import(`data:text/javascript;base64,${code}`);
});

after(async () => {
  server.closeAllConnections();
  await new Promise((done) => server.close(done));
});

test('таймаут действует, пока читается тело: 200 + начало JSON → ошибка 408', { timeout: 5000 }, async () => {
  const started = Date.now();
  await assert.rejects(client.request('/partial-body', { timeoutMs: 300 }), (err: any) => {
    assert.ok(err instanceof client.ApiError, 'ожидалась ApiError');
    assert.equal(err.status, 408);
    assert.equal(err.code, 'TIMEOUT');
    return true;
  });
  assert.ok(Date.now() - started < 3000, 'запрос должен завершиться сразу после таймаута');
});

test('таймаут до заголовков по-прежнему 408', { timeout: 5000 }, async () => {
  await assert.rejects(client.request('/no-headers', { timeoutMs: 300 }), (err: any) => err.status === 408);
});

test('отмена при смене фильтра во время чтения тела — AbortError, без сообщения об ошибке', { timeout: 5000 }, async () => {
  const ctrl = new AbortController();
  setTimeout(() => ctrl.abort(), 150);
  await assert.rejects(client.request('/partial-body', { signal: ctrl.signal, timeoutMs: 5000 }), (err: any) => {
    assert.equal(err.name, 'AbortError');
    assert.ok(!(err instanceof client.ApiError), 'отмена не должна превращаться в ApiError');
    return true;
  });
});

test('медленное, но полное тело в пределах таймаута читается', { timeout: 5000 }, async () => {
  const { data, status } = await client.request('/slow-ok', { timeoutMs: 2000 });
  assert.equal(status, 200);
  assert.deepEqual(data, { status: 'ok' });
});

test('ошибка API с JSON по-прежнему разбирается', { timeout: 5000 }, async () => {
  await assert.rejects(client.request('/invalid', { timeoutMs: 2000 }), (err: any) => {
    assert.equal(err.status, 422);
    assert.equal(err.code, 'VALIDATION_ERROR');
    assert.equal(err.message, 'Сумма часов не совпадает');
    return true;
  });
});
