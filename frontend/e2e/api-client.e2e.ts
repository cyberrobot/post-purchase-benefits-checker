import { test, expect } from '@playwright/test';
test('browser traverses real same-origin route to controlled upstream', async ({ page }) => {
  await page.goto('/');
  for (const [model, status, outcome] of [
    ['SKU', 200, 'resolved'],
    ['POPULATED', 200, 'resolved'],
    ['UNSAFE', 502, undefined],
    ['UNKNOWN', 200, 'unresolved_identity'],
    ['RATE', 429, undefined],
    ['OFFLINE', 502, undefined],
  ] as const) {
    const result = await page.evaluate(async (model) => {
      const response = await fetch('/api/eligibility/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: 'must-not-forward' },
        body: JSON.stringify({
          brand: 'Example',
          model,
          retailer: 'Shop',
          purchase_date: '2026-10-01',
          purchase_price: '799.99',
        }),
      });
      return {
        status: response.status,
        body: await response.json(),
        id: response.headers.get('x-request-id'),
        retry: response.headers.get('retry-after'),
        contentType: response.headers.get('content-type'),
        cacheControl: response.headers.get('cache-control'),
      };
    }, model);
    expect(result.status).toBe(status);
    expect(result.id).toMatch(/^[0-9a-f-]{36}$/);
    if (outcome) expect(result.body.outcome).toBe(outcome);
    if (model === 'POPULATED') {
      expect(result.body.promotions[0]).toMatchObject({
        promotion_name: 'Example populated promotion',
        claim_window: { status: 'open', opens_on: '2026-10-01', deadline_on: '2026-11-30' },
        requirements: [{ requirement_type: 'receipt', description: 'Keep your receipt.' }],
      });
    }
    if (model === 'UNSAFE') {
      expect(result.body).toMatchObject({ status: 502, code: 'upstream_unavailable' });
      expect(result.contentType).toContain('application/problem+json');
      expect(result.cacheControl).toBe('no-store');
      expect(JSON.stringify(result.body)).not.toMatch(
        /reviewer:secret|unsafe\.example|Example populated promotion|promotions/i,
      );
    }
    if (model === 'RATE') {
      expect(result.body.code).toBe('rate_limited');
      expect(result.retry).toBe('15');
    }
    if (model === 'OFFLINE') expect(result.body.code).toBe('upstream_unavailable');
  }
});
