/** @jest-environment node */
import { checkPurchaseResponseSchema, purchaseRequestSchema } from './eligibility.contract';
import { purchase, resolved, unresolved } from './fixtures';
import { populated, populatedClaim } from './promotion.fixture';
it.each([resolved, unresolved, populated, populatedClaim])(
  'accepts backend success and retains required fields',
  (value) => {
    expect(checkPurchaseResponseSchema.parse(value)).toEqual(value);
  },
);
it.each(['ELIGIBLE', 'POTENTIALLY_ELIGIBLE', 'NOT_ELIGIBLE', 'CLAIM_NOT_YET_OPEN', 'EXPIRED'])(
  'supports classification %s',
  (classification) => {
    const value = structuredClone(populated);
    value.promotions[0].eligibility.classification = classification;
    expect(checkPurchaseResponseSchema.safeParse(value).success).toBe(true);
  },
);
it.each([
  { ...purchase, purchase_date: '2026-02-29' },
  { ...purchase, purchase_price: 12.5 },
  { ...purchase, purchase_price: '01.00' },
  { ...purchase, purchase_date: '2026-10-01T00:00:00Z' },
  { ...purchase, brand: '  ' },
  { ...purchase, extra: true },
])('rejects malformed request', (value) =>
  expect(purchaseRequestSchema.safeParse(value).success).toBe(false),
);
it('rejects broken nested contracts and supports harmless additions', () => {
  const value = structuredClone(populated);
  delete (value.promotions[0] as Partial<(typeof value.promotions)[0]>).provenance;
  expect(checkPurchaseResponseSchema.safeParse(value).success).toBe(false);
  expect(checkPurchaseResponseSchema.parse({ ...resolved, future: true })).toEqual(resolved);
});
it('preserves date and decimal strings', () =>
  expect(purchaseRequestSchema.parse(purchase)).toEqual(purchase));

const sourceLocations = ['official', 'claim', 'source'] as const;
function withSourceUrl(location: (typeof sourceLocations)[number], url: string) {
  const value = structuredClone(populated);
  const promotion = value.promotions[0];
  if (location === 'official') promotion.provenance.official_source_url = url;
  else if (location === 'claim') promotion.provenance.claim_url = url;
  else promotion.sources[0].url = url;
  return value;
}
it.each(sourceLocations)('accepts and preserves HTTP(S) evidence at %s', (location) => {
  for (const url of ['http://example.com:8080/a?q=1#part', 'HTTPS://Example.com:443/%61']) {
    const value = withSourceUrl(location, url);
    expect(checkPurchaseResponseSchema.parse(value)).toEqual(value);
  }
});
it.each(sourceLocations)('rejects unsafe evidence at %s', (location) => {
  for (const url of [
    'javascript:alert(1)',
    'data:text/plain,hi',
    'file:///tmp/a',
    '//example.com/a',
    '/a',
    'https://user:pass@example.com/a',
    'https://user@example.com',
    'https://@example.com',
    'https:///a',
    'https://',
    'https://example.com:0',
    'https://example.com:65536',
    'https://example.com:invalid',
    'https://example.com/a b',
    'https://example.com/\npath',
    'https://example.com/\u0000',
    'https://[broken',
  ])
    expect(checkPurchaseResponseSchema.safeParse(withSourceUrl(location, url)).success).toBe(false);
});
it.each(sourceLocations)('rejects Unicode whitespace in evidence at %s', (location) => {
  expect(
    checkPurchaseResponseSchema.safeParse(withSourceUrl(location, 'https://example.com/\u0085path'))
      .success,
  ).toBe(false);
});
