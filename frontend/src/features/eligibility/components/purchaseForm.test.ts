import {
  completion,
  failure,
  requestFromDraft,
  todayInLondon,
  validatePurchase,
} from './purchaseForm';
import { purchaseRequestSchema } from '@/lib/api/eligibility.contract';
import { ApiError } from '@/lib/api/errors';
import { populatedClaim } from '@/lib/api/promotion.fixture';
const draft = {
  brand: 'Any brand',
  model: 'Sku./-123 AB',
  retailer: 'Any retailer',
  purchase_date: '2024-02-29',
};
it.each([
  ['2026-03-29T23:30:00Z', '2026-03-30'],
  ['2026-10-25T00:30:00Z', '2026-10-25'],
  ['2026-01-01T23:30:00Z', '2026-01-01'],
  ['2026-10-20T23:30:00Z', '2026-10-21'],
])('uses the Europe/London calendar date at %s', (instant, expected) => {
  expect(todayInLondon(new Date(instant))).toBe(expected);
});
it('rejects future purchases only in the form, preserving the shared calendar contract', () => {
  const future = { ...draft, purchase_date: '2024-03-01' };
  expect(validatePurchase(future, '2024-02-29').purchase_date).toMatch(/today or earlier/);
  expect(validatePurchase(draft, '2024-02-29')).toEqual({});
  expect(purchaseRequestSchema.safeParse(future).success).toBe(true);
});
it.each(['brand', 'model', 'retailer'] as const)(
  'validates %s boundary input without changing SKU meaning',
  (field) => {
    for (const value of [' ', '\u3000', 'a'.repeat(256), 'bad\u0001value'])
      expect(validatePurchase({ ...draft, [field]: value }, '2024-02-29')[field]).toBeDefined();
    expect(validatePurchase({ ...draft, [field]: 'a'.repeat(255) }, '2024-02-29')).toEqual({});
    expect(requestFromDraft(draft).model).toBe('Sku./-123 AB');
  },
);
it.each(['£799.99', '1,000.00', '1e3', '-1', '01', '1.234', '1000000000000', ' '])(
  'rejects ambiguous or unsupported money %s',
  (price) => {
    expect(
      validatePurchase({ ...draft, purchase_price: price }, '2024-02-29').purchase_price,
    ).toMatch(/GBP amount/);
  },
);
it.each(['0', '799.99', '999999999999.99'])('preserves exact wire money %s', (price) => {
  expect(validatePurchase({ ...draft, purchase_price: price }, '2024-02-29')).toEqual({});
  expect(requestFromDraft({ ...draft, purchase_price: price })).toEqual({
    ...draft,
    purchase_price: price,
  });
});
it('omits optional blank price entirely', () => {
  expect(requestFromDraft({ ...draft, purchase_price: '' })).toEqual(draft);
});
it('groups all reported classifications with accurate counts and no reward calculation', () => {
  if (populatedClaim.outcome !== 'resolved') throw new Error('fixture');
  const promotion = populatedClaim.promotions[0];
  const classifications = [
    'ELIGIBLE',
    'POTENTIALLY_ELIGIBLE',
    'NOT_ELIGIBLE',
    'CLAIM_NOT_YET_OPEN',
    'EXPIRED',
    'NOT_ELIGIBLE',
  ] as const;
  const result = completion({
    ...populatedClaim,
    promotions: classifications.map((classification) => ({
      ...promotion,
      eligibility: { ...promotion.eligibility, classification },
    })),
  });
  expect(result).toEqual([
    '1 promotion: meets recorded eligibility rules; this is not an approved or paid claim.',
    '1 promotion: may qualify; more evidence or information could be required.',
    '2 promotions: does not meet recorded rules.',
    '1 promotion: claim period has not opened.',
    '1 promotion: claim period has expired.',
  ]);
});
it.each(['brand', 'model', 'retailer'] as const)(
  'describes both unresolved %s statuses without IDs or server text',
  (field) => {
    for (const status of ['not_found', 'ambiguous'] as const) {
      const result = completion({
        outcome: 'unresolved_identity',
        evaluation_date: '2026-10-21',
        unresolved_identity: {
          field,
          status,
          candidate_ids: ['00000000-0000-0000-0000-000000000009'],
        },
        explanation: ['<script>unsafe</script>'],
      }).join(' ');
      expect(result).toMatch(status === 'ambiguous' ? /more specific/ : /could not be found/);
      expect(result).not.toMatch(/00000000|script|ineligible/);
    }
  },
);
it.each([undefined, '<script>unsafe</script>', 'bad\nreference', 'a'.repeat(100)])(
  'omits unsafe/missing support reference %s',
  (id) => {
    expect(failure(new ApiError('server', 500, 'internal', id))).toBe(
      'The checker encountered a service problem. Please try again.',
    );
  },
);
it('includes a validated opaque reference', () => {
  expect(
    failure(new ApiError('unavailable', 503, undefined, '00000000-0000-0000-0000-000000000009')),
  ).toContain('Support reference: 00000000-0000-0000-0000-000000000009');
});
