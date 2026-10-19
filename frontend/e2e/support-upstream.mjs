import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { createServer } from 'node:https';
import { createServer as createHttpServer } from 'node:http';
const id = '00000000-0000-0000-0000-000000000009';
const server = createServer(
  {
    key: readFileSync(resolve('e2e/certs/localhost-key.pem')),
    cert: readFileSync(resolve('e2e/certs/localhost-cert.pem')),
  },
  async (req, res) => {
    if (req.url === '/health') {
      res.end('ready');
      return;
    }
    let text = '';
    for await (const chunk of req) text += chunk;
    const purchase = JSON.parse(text);
    if (
      req.url !== '/api/v1/eligibility/check' ||
      req.method !== 'POST' ||
      req.headers.authorization ||
      req.headers.cookie ||
      purchase.purchase_price !== '799.99'
    ) {
      res.writeHead(500);
      res.end('{}');
      return;
    }
    if (purchase.model === 'OFFLINE') {
      req.socket.destroy();
      return;
    }
    let status = 200,
      body;
    if (purchase.model === 'RATE') {
      status = 429;
      body = {
        type: 'about:blank',
        title: 'Rate limited',
        status,
        detail: 'Try later.',
        code: 'rate_limited',
        request_id: id,
      };
    } else if (purchase.model === 'UNKNOWN')
      body = {
        outcome: 'unresolved_identity',
        evaluation_date: '2026-10-08',
        unresolved_identity: { field: 'model', status: 'not_found', candidate_ids: [] },
        explanation: ['Model not found.'],
      };
    else
      body = {
        outcome: 'resolved',
        evaluation_date: '2026-10-08',
        resolved_identity: { manufacturer_id: id, retailer_id: id, product_id: id },
        promotions: [],
        no_match_reason: 'no_matching_published_promotions',
        explanation: ['No matching promotion.'],
      };
    res.writeHead(status, {
      'Content-Type': status === 200 ? 'application/json' : 'application/problem+json',
      'X-Request-ID': id,
      ...(status === 429 ? { 'Retry-After': '15' } : {}),
    });
    res.end(JSON.stringify(body));
  },
);
server.listen(3102, '127.0.0.1');
const healthServer = createHttpServer((_req, res) => res.end('ready'));
healthServer.listen(3103, '127.0.0.1');
for (const signal of ['SIGTERM', 'SIGINT'])
  process.on(signal, () => {
    healthServer.close();
    server.close(() => process.exit(0));
  });
