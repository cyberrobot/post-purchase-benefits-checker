import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { setTimeout as delay } from 'node:timers/promises';

const port = 3100;
const server = spawn(
  process.execPath,
  ['node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', String(port)],
  { stdio: ['ignore', 'pipe', 'pipe'] },
);
let logs = '';
for (const stream of [server.stdout, server.stderr]) {
  stream.on('data', (chunk) => {
    logs += chunk;
  });
}
server.on('error', (error) => {
  logs += error.message;
});

try {
  let response;
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    assert.ok(
      server.exitCode === null && server.signalCode === null,
      `Server exited early: code=${server.exitCode}, signal=${server.signalCode}`,
    );
    try {
      response = await fetch(`http://127.0.0.1:${port}/`, { signal: AbortSignal.timeout(2000) });
      break;
    } catch {
      await delay(250);
    }
  }
  assert.ok(response, 'Server did not become ready within 30 seconds');
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /<html[^>]*lang="en-GB"/);
  assert.match(html, /<title>BenefitScout<\/title>/);
  assert.match(html, /<meta name="description" content="Check your purchase details/);
  assert.match(html, /<main[\s>]/);
  assert.match(html, /<h1[^>]*>Find benefits from a /);
  assert.match(html, /Find My Benefits/);
  console.log(
    'Production smoke passed: GET / returned 200 with server-rendered content and metadata.',
  );
} catch (error) {
  console.error(logs);
  throw error;
} finally {
  const exited = once(server, 'exit');
  if (server.exitCode === null && server.signalCode === null) {
    server.kill('SIGTERM');
    const force = setTimeout(() => server.kill('SIGKILL'), 5000);
    await exited;
    clearTimeout(force);
  }
}
