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
  expect(withPrice.guidance.join(' ')).toContain('no field for purchase country');
  expect(withPrice.guidance.join(' ')).not.toMatch(/purchase channel|product condition/);
  expect(withPrice.groups[1].items).toHaveLength(2);
});
it.each([
  ['NOT_ELIGIBLE', 'retailer_mismatch', 'retailer', 0],
  ['POTENTIALLY_ELIGIBLE', 'country_unknown', 'country', 1],
] as const)(
  'groups authoritative %s reasons without individual evaluations',
  (classification, code, rule_kind, groupIndex) => {
    const view = explain({ classification, reasons: [{ code, rule_kind }], rule_evaluations: [] });
    expect(view.groups[groupIndex].items.map((item) => item.text)).toEqual([reasonLabels[code]]);
    expect(view.groups[groupIndex].decisive).toBe(true);
  },
);
it('matches overlapping reason and evaluation occurrences without losing repeated or supplementary checks', () => {
  const view = explain({
    classification: 'NOT_ELIGIBLE',
    reasons: [
      { code: 'retailer_mismatch', rule_kind: 'retailer' },
      { code: 'purchase_price_below_minimum', rule_kind: 'purchase_price' },
      { code: 'retailer_mismatch', rule_kind: 'retailer' },
    ],
    rule_evaluations: [
      { kind: 'retailer', status: 'not_satisfied', reason_code: 'retailer_mismatch' },
      {
        kind: 'purchase_price',
        status: 'not_satisfied',
        reason_code: 'purchase_price_below_minimum',
      },
      { kind: 'country', status: 'unknown', reason_code: 'country_unknown' },
      { kind: 'retailer', status: 'not_satisfied', reason_code: 'retailer_mismatch' },
      { kind: 'retailer', status: 'not_satisfied', reason_code: 'retailer_mismatch' },
      { kind: 'purchase_date', status: 'not_satisfied', reason_code: 'purchase_date_after_end' },
      { kind: 'product', status: 'satisfied', reason_code: 'product_match' },
    ],
  });
  expect(view.groups[0].items.map((item) => item.text)).toEqual([
    reasonLabels.retailer_mismatch,
    reasonLabels.purchase_price_below_minimum,
    reasonLabels.retailer_mismatch,
    reasonLabels.retailer_mismatch,
    reasonLabels.purchase_date_after_end,
  ]);
  expect(new Set(view.groups[0].items.map((item) => item.key)).size).toBe(5);
  expect(view.groups[1].items.map((item) => item.text)).toEqual([reasonLabels.country_unknown]);
  expect(view.groups[2].items.map((item) => item.text)).toEqual([reasonLabels.product_match]);
});
it.each([
  [
    'purchase_channel_unknown',
    'purchase_channel',
    'purchase channel',
    ['product condition', 'purchase country', 'optional purchase price'],
  ],
  [
    'condition_unknown',
    'condition',
    'product condition',
    ['purchase channel', 'purchase country', 'optional purchase price'],
  ],
  [
    'country_unknown',
    'country',
    'purchase country',
    ['purchase channel', 'product condition', 'optional purchase price'],
  ],
  [
    'purchase_price_unknown',
    'purchase_price',
    'optional purchase price',
    ['purchase channel', 'product condition', 'purchase country'],
  ],
] as const)('gives guidance only for %s', (code, rule_kind, included, excluded) => {
  const view = explain({
    classification: 'POTENTIALLY_ELIGIBLE',
    reasons: [{ code, rule_kind }],
    rule_evaluations: [],
  });
  const guidance = view.guidance.join(' ');
  expect(guidance).toContain(included);
  for (const other of excluded) expect(guidance).not.toContain(other);
});
it('retains only the unsupported fields present in combined unknown reasons, in backend order', () => {
  const view = explain({
    classification: 'POTENTIALLY_ELIGIBLE',
    reasons: [
      { code: 'country_unknown', rule_kind: 'country' },
      { code: 'purchase_channel_unknown', rule_kind: 'purchase_channel' },
    ],
    rule_evaluations: [],
  });
  expect(view.guidance).toEqual([
    'The checker currently has no field for purchase country. Review the official terms for this unassessed fact.',
    'The checker currently has no field for purchase channel. Review the official terms for this unassessed fact.',
  ]);
});
it('does not suggest adding price to reverse a known failure, including contradictory potential evidence', () => {
  for (const classification of ['NOT_ELIGIBLE', 'POTENTIALLY_ELIGIBLE'] as const) {
    const view = explain({
      classification,
      reasons: [{ code: 'purchase_price_unknown', rule_kind: 'purchase_price' }],
      rule_evaluations: [
        { kind: 'retailer', status: 'not_satisfied', reason_code: 'retailer_mismatch' },
      ],
    });
    expect(view.guidance.join(' ')).not.toContain('add the optional purchase price');
    expect(view.summary).toBe(statuses.find((status) => status.value === classification)!.meaning);
  }
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
