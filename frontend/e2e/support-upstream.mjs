import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { createServer } from 'node:https';
import { createServer as createHttpServer } from 'node:http';
const id = '00000000-0000-0000-0000-000000000009';
function populatedResponse(unsafe = false) {
  const source = (sourceId, role, url) => ({
    source_id: sourceId,
    role,
    url,
    source_type: 'web_page',
    retrieved_at: '2026-10-01T00:00:00Z',
    verified_at: '2026-10-02T00:00:00Z',
  });
  const safeClaimUrl = 'https://example.com/claim';
  const unsafeClaimUrl = 'https://reviewer:secret@unsafe.example/claim';
  return {
    outcome: 'resolved',
    evaluation_date: '2026-10-08',
    resolved_identity: {
      manufacturer_id: '00000000-0000-0000-0000-000000000001',
      retailer_id: '00000000-0000-0000-0000-000000000002',
      product_id: '00000000-0000-0000-0000-000000000003',
    },
    promotions: [
      {
        promotion_id: '00000000-0000-0000-0000-000000000004',
        promotion_variant_id: '00000000-0000-0000-0000-000000000005',
        promotion_name: 'Example populated promotion',
        variant_name: null,
        promotion_status: 'active',
        eligibility: {
          classification: 'ELIGIBLE',
          reasons: [
            { code: 'all_configured_rules_satisfied', rule_kind: null },
            { code: 'claim_window_open', rule_kind: null },
          ],
          rule_evaluations: [
            { kind: 'product', status: 'satisfied', reason_code: 'product_match' },
          ],
          claim_window_status: 'open',
        },
        claim_window: { status: 'open', opens_on: '2026-10-01', deadline_on: '2026-11-30' },
        benefits: [
          {
            benefit_id: '00000000-0000-0000-0000-000000000006',
            benefit_type: 'cashback',
            name: 'Cashback',
            description: null,
            cashback_reward_gbp: '10.00',
            reward_unavailable_reason: null,
            reward_unavailable_explanation: null,
          },
        ],
        requirements: [{ requirement_type: 'receipt', description: 'Keep your receipt.' }],
        last_verified_at: '2026-10-02T00:00:00Z',
        provenance: {
          official_source_url: 'https://example.com/offer',
          source_type: 'web_page',
          retrieved_at: '2026-10-01T00:00:00Z',
          verified_at: '2026-10-02T00:00:00Z',
          claim_url: unsafe ? unsafeClaimUrl : safeClaimUrl,
        },
        sources: [
          source('00000000-0000-0000-0000-000000000007', 'primary', 'https://example.com/offer'),
          source(
            '00000000-0000-0000-0000-000000000008',
            'claim',
            unsafe ? unsafeClaimUrl : safeClaimUrl,
          ),
        ],
        explanation: ['The recorded eligibility rules match this purchase.'],
      },
    ],
    no_match_reason: null,
    explanation: [],
  };
}
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
      !['brand', 'model', 'retailer', 'purchase_date'].every(
        (key) => typeof purchase[key] === 'string',
      ) ||
      Object.keys(purchase).some(
        (key) => !['brand', 'model', 'retailer', 'purchase_date', 'purchase_price'].includes(key),
      ) ||
      (purchase.purchase_price != null && purchase.purchase_price !== '799.99')
    ) {
      res.writeHead(500);
      res.end('{}');
      return;
    }
    if (purchase.model === 'SLOW' || purchase.model === 'TIMEOUT')
      await new Promise((resolve) =>
        setTimeout(resolve, purchase.model === 'TIMEOUT' ? 9000 : 4000),
      );
    if (purchase.model === 'MALFORMED') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end('{bad json');
      return;
    }
    if (purchase.model === 'OFFLINE') {
      req.socket.destroy();
      return;
    }
    if (
      purchase.model === 'POPULATED' ||
      purchase.model === 'NOT_ELIGIBLE' ||
      purchase.model === 'UNSAFE' ||
      purchase.model === 'MIXED'
    ) {
      const populated = populatedResponse(purchase.model === 'UNSAFE');
      if (purchase.model === 'NOT_ELIGIBLE')
        populated.promotions[0].eligibility.classification = 'NOT_ELIGIBLE';
      if (purchase.model === 'MIXED') {
        const original = populated.promotions[0];
        populated.promotions = [
          'ELIGIBLE',
          'POTENTIALLY_ELIGIBLE',
          'NOT_ELIGIBLE',
          'CLAIM_NOT_YET_OPEN',
          'EXPIRED',
          'NOT_ELIGIBLE',
        ].map((classification, index) => ({
          ...original,
          promotion_id: `00000000-0000-0000-0000-${String(index + 10).padStart(12, '0')}`,
          eligibility: { ...original.eligibility, classification },
        }));
      }
      res.writeHead(200, {
        'Content-Type': 'application/json',
        'X-Request-ID': id,
      });
      res.end(JSON.stringify(populated));
      return;
    }
    let status = 200,
      body;
    if (['RATE', 'UNAVAILABLE', 'BAD_GATEWAY'].includes(purchase.model)) {
      status = purchase.model === 'RATE' ? 429 : purchase.model === 'UNAVAILABLE' ? 503 : 502;
      body = {
        type: 'about:blank',
        title: 'Rate limited',
        status,
        detail: 'Try later.',
        code: 'rate_limited',
        request_id: id,
      };
    } else if (purchase.model === 'UNKNOWN' || purchase.model === 'AMBIGUOUS')
      body = {
        outcome: 'unresolved_identity',
        evaluation_date: '2026-10-08',
        unresolved_identity: {
          field: 'model',
          status: purchase.model === 'AMBIGUOUS' ? 'ambiguous' : 'not_found',
          candidate_ids: purchase.model === 'AMBIGUOUS' ? [id] : [],
        },
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
