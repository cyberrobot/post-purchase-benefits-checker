import { test, expect } from '@playwright/test';
test('browser traverses real same-origin route to controlled upstream', async ({ page }) => {
  await page.goto('/');
  for (const [model, status, outcome] of [
    ['SKU', 200, 'resolved'],
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
      };
    }, model);
    expect(result.status).toBe(status);
    expect(result.id).toMatch(/^[0-9a-f-]{36}$/);
    if (outcome) expect(result.body.outcome).toBe(outcome);
    if (model === 'RATE') {
      expect(result.body.code).toBe('rate_limited');
      expect(result.retry).toBe('15');
    }
    if (model === 'OFFLINE') expect(result.body.code).toBe('upstream_unavailable');
  }
});
