import {
  completion,
  failure,
  requestFromDraft,
  todayInLondon,
  validatePurchase,
} from './purchaseForm';
import { purchaseRequestSchema, type CheckPurchaseResponse } from '@/lib/api/eligibility.contract';
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
it('counts six variant matches across five promotions and preserves every classification', () => {
  if (populatedClaim.outcome !== 'resolved') throw new Error('fixture');
  const promotion = populatedClaim.promotions[0];
  const cases = [
    ['ELIGIBLE', 'open', '2026-10-01', '2026-11-30'],
    ['POTENTIALLY_ELIGIBLE', null, null, null],
    ['NOT_ELIGIBLE', 'open', '2026-10-01', '2026-11-30'],
    ['CLAIM_NOT_YET_OPEN', 'not_yet_open', '2026-10-09', '2026-11-30'],
    ['EXPIRED', 'expired', '2026-10-01', '2026-10-07'],
    ['NOT_ELIGIBLE', 'open', '2026-10-01', '2026-11-30'],
  ] as const;
  const promotions: Extract<CheckPurchaseResponse, { outcome: 'resolved' }>['promotions'] =
    cases.map(([classification, status, opens_on, deadline_on], index) => ({
      ...promotion,
      promotion_id: `00000000-0000-0000-0000-${String(index === 5 ? 12 : index + 10).padStart(12, '0')}`,
      promotion_variant_id: `00000000-0000-0000-0000-${String(index + 100).padStart(12, '0')}`,
      eligibility: {
        classification,
        reasons:
          classification === 'NOT_ELIGIBLE'
            ? [{ code: 'purchase_date_before_start', rule_kind: 'purchase_date' }]
            : [
                { code: 'all_configured_rules_satisfied', rule_kind: null },
                { code: `claim_window_${status ?? 'unspecified'}`, rule_kind: null },
              ],
        rule_evaluations:
          classification === 'NOT_ELIGIBLE'
            ? [
                {
                  kind: 'purchase_date',
                  status: 'not_satisfied',
                  reason_code: 'purchase_date_before_start',
                },
              ]
            : promotion.eligibility.rule_evaluations,
        claim_window_status: status,
      },
      claim_window: status === null ? null : { status, opens_on, deadline_on },
      explanation: [],
    }));
  expect(promotions).toHaveLength(6);
  expect(new Set(promotions.map((match) => match.promotion_id)).size).toBe(5);
  expect(new Set(promotions.map((match) => match.promotion_variant_id)).size).toBe(6);
  const result = completion({ ...populatedClaim, promotions });
  expect(result).toEqual([
    '1 promotion match: meets recorded eligibility rules; this is not an approved or paid claim.',
    '1 promotion match: may qualify; more evidence or information could be required.',
    '2 promotion matches: does not meet recorded rules.',
    '1 promotion match: claim period has not opened.',
    '1 promotion match: claim period has expired.',
  ]);
  expect(result.join(' ')).not.toMatch(
    /confirmed benefits?|guaranteed|cashback|claim approved|claimable|£/i,
  );
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
