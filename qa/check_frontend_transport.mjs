/** Real frontend transport module against a synthetic loopback HTTP server.
 * This is Node-level network QA, NOT a browser or responsive E2E test.
 * Run after `npm ci --prefix web`: node qa/check_frontend_transport.mjs
 * No frontend source changes; known failures are reported with a nonzero exit.
 */
import assert from 'node:assert/strict';
import http from 'node:http';
import { createRequire } from 'node:module';
import { mkdtemp, writeFile, rm, mkdir } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

const root = resolve(import.meta.dirname, '..');
const require = createRequire(join(root, 'web/package.json'));
const { build } = require('esbuild');
await mkdir(join(root, 'data'), { recursive: true });
const temporary = await mkdtemp(join(root, 'data/transport-'));
const observations = [];
let behavior = 'normal';
let responseStatus = 200;
const server = http.createServer((req, res) => {
  if (behavior === 'no-headers') return;
  if (behavior === 'partial-body') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.write('{"status":');
    return;
  }
  res.writeHead(responseStatus, { 'Content-Type': behavior === 'proxy' ? 'text/html' : 'application/json', 'Retry-After': '3' });
  res.end(behavior === 'proxy' ? '<h1>Bad Gateway</h1>' : JSON.stringify({ code: 'SYNTHETIC_ERROR', message: 'Synthetic transport check' }));
});
await new Promise((done) => server.listen(0, '127.0.0.1', done));
const base = `http://127.0.0.1:${server.address().port}`;
// Only the timers needed by the unchanged request module; there is no DOM.
globalThis.window = { setTimeout, clearTimeout };
try {
  const bundle = await build({ entryPoints: [join(root, 'web/src/api/client.ts')],
    bundle: true, write: false, platform: 'node', format: 'esm',
    define: { 'import.meta.env': JSON.stringify({ VITE_API_BASE_URL: base }) } });
  const file = join(temporary, 'client.mjs');
  await writeFile(file, bundle.outputFiles[0].contents);
  const { api, DEFAULT_TIMEOUT_MS } = await import(pathToFileURL(file).href);
  for (const status of [400, 404, 422, 429, 500, 502, 503]) {
    responseStatus = status;
    await assert.rejects(api.health(), (error) => error.status === status && (status !== 429 || error.retryAfter === 3));
    observations.push({ name: `HTTP ${status} JSON`, passed: true });
  }
  behavior = 'proxy'; responseStatus = 502;
  await assert.rejects(api.health(), (error) => error.isNetwork && !error.message.includes('<h1>'));
  observations.push({ name: 'HTML proxy error maps to server unavailable', passed: true });

  behavior = 'no-headers';
  const before = Date.now();
  await assert.rejects(api.health(), (error) => error.status === 408);
  observations.push({ name: 'timeout before headers', passed: true, elapsed_ms: Date.now() - before });

  behavior = 'partial-body';
  const response = api.health().then(() => 'success', (error) => error.status === 408 ? 'timeout' : 'other-error');
  const outcome = await Promise.race([response, delay(DEFAULT_TIMEOUT_MS + 1200).then(() => 'pending-after-deadline')]);
  observations.push({ name: 'timeout while reading body', passed: outcome === 'timeout', outcome,
    owner: 'Damir', source: 'web/src/api/client.ts:115-153' });
  server.closeAllConnections();
  await response;
} finally {
  server.closeAllConnections();
  await new Promise((done) => server.close(done));
  // This is the exact fresh temporary directory allocated by this test.
  await rm(temporary, { recursive: true });
}
const report = { browser_e2e: false, synthetic_loopback_only: true,
  passed: observations.filter((x) => x.passed).length,
  failed: observations.filter((x) => !x.passed).length, observations };
await writeFile(join(root, 'data/frontend-transport.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
if (report.failed) process.exitCode = 1;
