import { populatedClaim } from '@/lib/api/promotion.fixture';
import { calendarDate, counts, gbp, selectPromotions, statuses } from './presentation';
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
