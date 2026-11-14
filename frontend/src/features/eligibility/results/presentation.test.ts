import { populatedClaim } from '@/lib/api/promotion.fixture';
import {
  calendarDate,
  counts,
  gbp,
  presentBenefit,
  presentClaimPeriod,
  selectPromotions,
  statuses,
} from './presentation';
const promotion = populatedClaim.outcome === 'resolved' ? populatedClaim.promotions[0] : never();
function never(): never {
  throw new Error('fixture');
}
it('counts variants independently, retains every classification and stable backend order', () => {
  const variants = [...statuses, statuses[4]].map((s, i) => ({
    ...promotion,
    promotion_variant_id: String(i),
    eligibility: { ...promotion.eligibility, classification: s.value },
  }));
  expect(variants).toHaveLength(6);
  expect(counts(variants)).toEqual({
    ELIGIBLE: 1,
    POTENTIALLY_ELIGIBLE: 1,
    CLAIM_NOT_YET_OPEN: 1,
    EXPIRED: 1,
    NOT_ELIGIBLE: 2,
  });
  expect(selectPromotions(variants, 'all')).toEqual(variants);
  expect(selectPromotions(variants, 'NOT_ELIGIBLE').map((p) => p.promotion_variant_id)).toEqual([
    '4',
    '5',
  ]);
  expect(counts([]).ELIGIBLE).toBe(0);
});
it('formats decimal strings without float rounding and calendar dates without timezone shifting', () => {
  expect(gbp('999999999999.99')).toBe('£999,999,999,999.99');
  expect(gbp('10.00100')).toBe('£10.00100');
  expect(calendarDate('0001-01-01')).toBe('01 Jan 0001');
  expect(calendarDate('2024-02-29')).toBe('29 Feb 2024');
});

it.each([
  ['10', '£10'],
  ['10.00', '£10.00'],
])('formats the exact recorded value %s', (wire, label) => {
  expect(gbp(wire)).toBe(label);
});

it.each([
  ['cashback', 'Cashback'],
  ['extended_warranty', 'Extended warranty'],
  ['free_gift', 'Free gift'],
] as const)('uses the %s category when the name is blank', (benefit_type, category) => {
  const description = '<img src=x>'.repeat(50);
  expect(
    presentBenefit({ ...promotion.benefits[0], benefit_type, name: '  ', description }, false),
  ).toMatchObject({ category, title: category, description, canRecheckWithPurchasePrice: false });
});

it.each([
  ['purchase_price_required_for_reward', false, 'Cashback amount not available yet', true],
  ['purchase_price_required_for_reward', true, 'Cashback amount not available yet', false],
  ['reward_not_configured', false, 'Cashback amount not available for this promotion', false],
  [null, false, 'Cashback amount not supplied', false],
] as const)(
  'handles missing cashback reason %s with price provided %s',
  (reason, price, label, canEdit) => {
    expect(
      presentBenefit(
        {
          ...promotion.benefits[0],
          cashback_reward_gbp: null,
          reward_unavailable_reason: reason,
          reward_unavailable_explanation: null,
        },
        price,
      ),
    ).toMatchObject({
      amountLabel: null,
      unavailableLabel: label,
      canRecheckWithPurchasePrice: canEdit,
    });
  },
);

it.each([
  ['open', 'Claim period was open when checked'],
  ['not_yet_open', 'Claim period had not opened when checked'],
  ['expired', 'Claim period had ended when checked'],
  [null, 'Claim timing not supplied'],
] as const)('shows the recorded %s timing even without dates', (status, timingLabel) => {
  expect(
    presentClaimPeriod({
      ...promotion,
      eligibility: { ...promotion.eligibility, claim_window_status: status },
      claim_window: null,
    }),
  ).toEqual({ timingLabel, opensOn: null, deadlineOn: null });
});

it('keeps evaluated status and projected dates if the projected status disagrees', () => {
  expect(
    presentClaimPeriod({
      ...promotion,
      eligibility: { ...promotion.eligibility, claim_window_status: 'open' },
      claim_window: { status: 'expired', opens_on: '2026-10-08', deadline_on: '2026-10-08' },
    }),
  ).toEqual({
    timingLabel: 'Claim period was open when checked',
    opensOn: '2026-10-08',
    deadlineOn: '2026-10-08',
  });
});

it.each([
  ['fixed window opening boundary', 'open', '2026-10-08', '2026-11-30'],
  ['relative window deadline boundary', 'open', '2026-09-08', '2026-10-08'],
  ['minimum-wait opening boundary', 'not_yet_open', '2026-10-09', '2026-11-30'],
] as const)('preserves backend %s projection at inclusive dates', (_case, status, opensOn, deadlineOn) => {
  expect(
    presentClaimPeriod({
      ...promotion,
      eligibility: { ...promotion.eligibility, claim_window_status: status },
      claim_window: { status, opens_on: opensOn, deadline_on: deadlineOn },
    }),
  ).toEqual({
    timingLabel: status === 'open' ? 'Claim period was open when checked' : 'Claim period had not opened when checked',
    opensOn,
    deadlineOn,
  });
});
