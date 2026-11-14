/** @jest-environment node */
import { promotionDetailsSchema } from './promotion-details.contract';
import { id, recordedTerms } from './promotion-details.fixture';
import { parsePublicSlug } from './promotion-slug';

it('preserves the complete multi-variant projection and nullable verification', () => {
  expect(promotionDetailsSchema.parse(recordedTerms)).toEqual(recordedTerms);
});

it.each(['A--b', 'a--b--c', 'a--', 'a--b\n', 'a--b%2F', 'a--_b', 'a'.repeat(256) + '--b'])(
  'rejects malformed public key %j',
  (value) => {
    expect(parsePublicSlug(value)).toBeUndefined();
  },
);

it.each([
  { status: 'review' },
  { public_slug: 'different--populated-promotion' },
  { sources: recordedTerms.sources.map((source) => ({ ...source, verified_at: '2026-10-02' })) },
  {
    sources: recordedTerms.sources.map((source) => ({
      ...source,
      url: 'https://secret@invalid.test',
    })),
  },
  { variants: [recordedTerms.variants[0], recordedTerms.variants[0]] },
  { purchase_window: { starts_on: '2026-02-29', ends_on: null } },
])('fails closed for invalid or inconsistent details', (patch) => {
  expect(promotionDetailsSchema.safeParse({ ...recordedTerms, ...patch }).success).toBe(false);
});

it.each([
  { kind: 'fixed_amount', amount_gbp: '1e2' },
  { kind: 'fixed_amount', amount_gbp: '1.25', percentage: '2.50' },
  { kind: 'product_specific', values: [{ product_id: id(19), amount_gbp: '1.25' }] },
  { kind: 'percentage', percentage: 1.25 },
])('validates reward discriminants, decimals and product association', (reward) => {
  const variant = recordedTerms.variants[0];
  expect(
    promotionDetailsSchema.safeParse({
      ...recordedTerms,
      variants: [{ ...variant, benefits: [{ ...variant.benefits[0], reward }] }],
    }).success,
  ).toBe(false);
});
