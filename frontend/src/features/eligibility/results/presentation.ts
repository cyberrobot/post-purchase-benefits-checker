import type { CheckPurchaseResponse } from '@/lib/api/eligibility.contract';
export type Promotion = Extract<
  CheckPurchaseResponse,
  { outcome: 'resolved' }
>['promotions'][number];
export type Classification = Promotion['eligibility']['classification'];
export const statuses: {
  value: Classification;
  label: string;
  icon: string;
  meaning: string;
  accent: string;
}[] = [
  {
    value: 'ELIGIBLE',
    label: 'Eligible',
    icon: '✓',
    meaning:
      'This purchase meets the recorded eligibility rules. This is not an approved or paid claim.',
    accent: 'border-success text-success bg-success-subtle',
  },
  {
    value: 'POTENTIALLY_ELIGIBLE',
    label: 'Potentially eligible',
    icon: '?',
    meaning: 'The recorded information does not establish eligibility with certainty.',
    accent: 'border-amber-700 text-amber-900 bg-amber-50',
  },
  {
    value: 'CLAIM_NOT_YET_OPEN',
    label: 'Claim not yet open',
    icon: '◷',
    meaning:
      'The recorded eligibility rules are met, but the claim period has not opened at the evaluation date.',
    accent: 'border-blue-700 text-blue-900 bg-blue-50',
  },
  {
    value: 'EXPIRED',
    label: 'Claim period expired',
    icon: '–',
    meaning: 'The recorded claim deadline has passed at the evaluation date.',
    accent: 'border-ink-muted text-ink-muted bg-surface-muted',
  },
  {
    value: 'NOT_ELIGIBLE',
    label: 'Not eligible',
    icon: '×',
    meaning: 'Does not meet one or more recorded eligibility conditions.',
    accent: 'border-red-700 text-red-900 bg-red-50',
  },
];
export function counts(promotions: Promotion[]) {
  return Object.fromEntries(
    statuses.map(({ value }) => [
      value,
      promotions.filter((p) => p.eligibility.classification === value).length,
    ]),
  ) as Record<Classification, number>;
}
export function selectPromotions(promotions: Promotion[], filter: Classification | 'all') {
  // Keep the backend's order, including multiple variants of one promotion.
  return promotions.filter((p) => filter === 'all' || p.eligibility.classification === filter);
}
export function calendarDate(value: string) {
  const [year, month, day] = value.split('-');
  const months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ];
  return `${day} ${months[Number(month) - 1]} ${year}`;
}
export function timestamp(value: string) {
  return (
    new Intl.DateTimeFormat('en-GB', {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: 'UTC',
    }).format(new Date(value)) + ' UTC'
  );
}
export function gbp(value: string) {
  const [whole, fraction] = value.split('.');
  return `£${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}${fraction === undefined ? '' : `.${fraction}`}`;
}
export function words(value: string) {
  return value.replaceAll('_', ' ');
}

const benefitCategories = {
  cashback: 'Cashback',
  extended_warranty: 'Extended warranty',
  free_gift: 'Free gift',
} satisfies Record<Promotion['benefits'][number]['benefit_type'], string>;

export function presentBenefit(benefit: Promotion['benefits'][number], hasPurchasePrice: boolean) {
  const category = benefitCategories[benefit.benefit_type];
  const title = benefit.name.trim() || category;
  const cashback = benefit.benefit_type === 'cashback';
  const amountLabel =
    cashback && benefit.cashback_reward_gbp !== null
      ? `${gbp(benefit.cashback_reward_gbp)} cashback`
      : null;
  const reason = benefit.reward_unavailable_reason;
  const unavailableLabel =
    !cashback || amountLabel
      ? null
      : {
          purchase_price_required_for_reward: 'Cashback amount not available yet',
          reward_not_configured: 'Cashback amount not available for this promotion',
          unspecified: 'Cashback amount not supplied',
        }[reason ?? 'unspecified'];
  return {
    category,
    title,
    amountLabel,
    description: benefit.description,
    unavailableLabel,
    unavailableExplanation: unavailableLabel
      ? benefit.reward_unavailable_explanation ||
        (reason === 'purchase_price_required_for_reward'
          ? 'The promotion uses the purchase price to work out the cashback amount.'
          : reason === 'reward_not_configured'
            ? 'Check the official terms for cashback details.'
            : null)
      : null,
    canRecheckWithPurchasePrice:
      Boolean(unavailableLabel) &&
      reason === 'purchase_price_required_for_reward' &&
      !hasPurchasePrice,
  };
}

const claimTimingLabels = {
  open: 'Claim period was open when checked',
  not_yet_open: 'Claim period had not opened when checked',
  expired: 'Claim period had ended when checked',
} satisfies Record<NonNullable<Promotion['eligibility']['claim_window_status']>, string>;

export function presentClaimPeriod(promotion: Promotion) {
  const timing = promotion.eligibility.claim_window_status;
  return {
    timingLabel: timing === null ? 'Claim timing not supplied' : claimTimingLabels[timing],
    opensOn: promotion.claim_window?.opens_on ?? null,
    deadlineOn: promotion.claim_window?.deadline_on ?? null,
  };
}
