/** @jest-environment node */
import { checkPurchaseResponseSchema, purchaseRequestSchema } from './eligibility.contract';
import { purchase, resolved, unresolved } from './fixtures';
import { populated } from './promotion.fixture';
it.each([resolved, unresolved, populated])(
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
