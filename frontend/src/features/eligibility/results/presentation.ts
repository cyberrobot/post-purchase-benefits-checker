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
