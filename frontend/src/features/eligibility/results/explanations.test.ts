import { promotionSchema, type PurchaseRequest } from '@/lib/api/eligibility.contract';
import { populatedClaim } from '@/lib/api/promotion.fixture';
import { explainPromotion, reasonLabels } from './explanations';
import { statuses, type Promotion } from './presentation';
const promotion = populatedClaim.outcome === 'resolved' ? populatedClaim.promotions[0] : null!;
const submittedPurchase: PurchaseRequest = {
  brand: 'Brand',
  model: 'Model',
  retailer: 'Shop',
  purchase_date: '2024-02-29',
};
const context = { evaluationDate: '2026-10-08', submittedPurchase };
const explain = (eligibility: Partial<Promotion['eligibility']>, extra: Partial<Promotion> = {}) =>
  explainPromotion(
    { ...promotion, ...extra, eligibility: { ...promotion.eligibility, ...eligibility } },
    context,
  );
it('exhaustively maps every validated decision and rule reason to readable copy', () => {
  const schema = promotionSchema.shape.eligibility.shape;
  expect(Object.keys(reasonLabels).sort()).toEqual(
    [...schema.reasons.element.shape.code.options].sort(),
  );
  expect(
    schema.rule_evaluations.element.shape.reason_code.options.every((code) => reasonLabels[code]),
  ).toBe(true);
  for (const label of Object.values(reasonLabels)) {
    expect(label).not.toMatch(/_/);
    expect(label).toMatch(/\.$/);
  }
});
it.each(statuses)(
  'keeps the reported $value despite contradictory evidence and lifecycle',
  (status) => {
    const view = explain(
      { classification: status.value, reasons: [], rule_evaluations: [] },
      { promotion_status: 'expired', claim_window: null },
    );
    expect(view.summary).toBe(status.meaning);
    expect(view.decisions).toEqual([]);
    expect(view.groups.every((group) => group.items.length === 0)).toBe(true);
    expect(view.evaluatedOn).toBe('As evaluated on 08 Oct 2026.');
  },
);
it('retains repeated failed kinds and independent unknown evidence in backend order', () => {
  const view = explain({
    classification: 'NOT_ELIGIBLE',
    reasons: [
      { code: 'purchase_date_after_end', rule_kind: 'purchase_date' },
      { code: 'purchase_date_before_start', rule_kind: 'purchase_date' },
    ],
    rule_evaluations: [
      { kind: 'purchase_date', status: 'not_satisfied', reason_code: 'purchase_date_after_end' },
      { kind: 'purchase_price', status: 'unknown', reason_code: 'purchase_price_unknown' },
      { kind: 'purchase_date', status: 'not_satisfied', reason_code: 'purchase_date_before_start' },
    ],
  });
  expect(view.decisions.map((item) => item.text)).toEqual([
    reasonLabels.purchase_date_after_end,
    reasonLabels.purchase_date_before_start,
  ]);
  expect(view.groups[0].items.map((item) => item.text)).toEqual(
    view.decisions.map((item) => item.text),
  );
  expect(view.groups[1].items[0].text).toBe(reasonLabels.purchase_price_unknown);
  expect(view.guidance.join(' ')).not.toMatch(/add the optional/);
});
it('distinguishes unspecified timing from missing purchase facts', () => {
  const view = explain(
    {
      classification: 'POTENTIALLY_ELIGIBLE',
      claim_window_status: null,
      reasons: [
        { code: 'all_configured_rules_satisfied', rule_kind: null },
        { code: 'claim_window_unspecified', rule_kind: null },
      ],
    },
    { claim_window: null },
  );
  expect(view.decisions.map((item) => item.text)).toContain(reasonLabels.claim_window_unspecified);
  expect(view.claimTiming).toBe('Claim period not supplied.');
  expect(view.guidance.join(' ')).not.toMatch(/price|receipt|missing/);
});
it('only suggests optional price when absent and refers unsupported facts to terms', () => {
  const data: Promotion = {
    ...promotion,
    eligibility: {
      ...promotion.eligibility,
      classification: 'POTENTIALLY_ELIGIBLE',
      reasons: [
        { code: 'purchase_price_unknown', rule_kind: 'purchase_price' },
        { code: 'country_unknown', rule_kind: 'country' },
      ],
      rule_evaluations: [
        { kind: 'purchase_price', status: 'unknown', reason_code: 'purchase_price_unknown' },
        { kind: 'country', status: 'unknown', reason_code: 'country_unknown' },
      ],
    },
  };
  expect(explainPromotion(data, context).guidance.join(' ')).toContain(
    'add the optional purchase price',
  );
  const withPrice = explainPromotion(data, {
    ...context,
    submittedPurchase: { ...submittedPurchase, purchase_price: '799.99' },
  });
  expect(withPrice.guidance.join(' ')).not.toContain('add the optional purchase price');
  expect(withPrice.guidance.join(' ')).toContain(
    'no fields for purchase channel, product condition or country',
  );
  expect(withPrice.groups[1].items).toHaveLength(2);
});
it.each(['open', 'not_yet_open', 'expired', null] as const)(
  'uses supplied claim status %s even without dates',
  (timing) => {
    const view = explain({ claim_window_status: timing }, { claim_window: null });
    expect(view.claimTiming).toBe(
      timing === null ? 'Claim period not supplied.' : reasonLabels[`claim_window_${timing}`],
    );
    expect(JSON.stringify(view)).not.toContain('2026-11-30');
  },
);
