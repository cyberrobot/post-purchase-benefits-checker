import type { PurchaseRequest } from '@/lib/api/eligibility.contract';
import { calendarDate, statuses, type Promotion } from './presentation';
type ReasonCode = Promotion['eligibility']['reasons'][number]['code'];
type Rule = Promotion['eligibility']['rule_evaluations'][number];
export const reasonLabels = {
  manufacturer_match: 'The manufacturer matches the recorded manufacturer conditions.',
  manufacturer_mismatch:
    "The manufacturer does not match this promotion's recorded manufacturer conditions.",
  product_match: 'The product model matches the recorded product conditions.',
  product_mismatch:
    "The product model does not match this promotion's recorded product conditions.",
  retailer_match: 'The retailer matches the recorded retailer conditions.',
  retailer_mismatch: "The retailer does not match this promotion's recorded retailer conditions.",
  purchase_channel_match: 'The purchase channel meets the recorded restriction.',
  purchase_channel_mismatch: 'The purchase channel does not meet the recorded restriction.',
  purchase_channel_unknown:
    'The purchase channel could not be assessed against the recorded restriction.',
  purchase_date_match: 'The purchase date is within the recorded qualifying purchase period.',
  purchase_date_before_start:
    'The purchase date is before the recorded qualifying purchase period.',
  purchase_date_after_end: 'The purchase date is after the recorded qualifying purchase period.',
  purchase_price_match: 'The purchase price meets the recorded price conditions.',
  purchase_price_below_minimum: 'The purchase price is below the recorded minimum.',
  purchase_price_above_maximum: 'The purchase price is above the recorded maximum.',
  purchase_price_unknown:
    "The purchase price could not be assessed against this promotion's rules.",
  condition_match: 'The product condition meets the recorded restriction.',
  condition_mismatch: 'The product condition does not meet the recorded restriction.',
  condition_unknown:
    'The product condition could not be assessed against the recorded restriction.',
  country_match: 'The purchase country meets the recorded restriction.',
  country_mismatch: 'The purchase country does not meet the recorded restriction.',
  country_unknown: 'The purchase country could not be assessed against the recorded restriction.',
  all_configured_rules_satisfied: 'All recorded eligibility conditions were satisfied.',
  claim_window_open: 'The recorded claim period is open at the evaluation date.',
  claim_window_not_yet_open: 'The claim period has not opened at the evaluation date.',
  claim_window_expired: 'The recorded claim period has ended at the evaluation date.',
  claim_window_unspecified:
    'The claim period could not be determined from the recorded information.',
} satisfies Record<ReasonCode, string>;
export const ruleStatusLabels = {
  satisfied: 'Recorded check passed',
  not_satisfied: 'Condition not met',
  unknown: 'Could not be assessed',
} satisfies Record<Rule['status'], string>;
export function explainPromotion(
  promotion: Promotion,
  context: { evaluationDate: string; submittedPurchase: PurchaseRequest },
) {
  const {
    classification,
    reasons,
    rule_evaluations: rules,
    claim_window_status: timing,
  } = promotion.eligibility;
  const groups = [
    { heading: 'Conditions not met', status: 'not_satisfied' },
    { heading: "Information we couldn't assess", status: 'unknown' },
    { heading: 'Recorded checks passed', status: 'satisfied' },
  ].map((group) => ({
    ...group,
    items: rules.flatMap((rule, index) =>
      rule.status === group.status
        ? [{ key: String(index), text: reasonLabels[rule.reason_code] }]
        : [],
    ),
  }));
  const claimTiming =
    timing === null
      ? 'Claim period not supplied.'
      : reasonLabels[
          {
            open: 'claim_window_open',
            not_yet_open: 'claim_window_not_yet_open',
            expired: 'claim_window_expired',
          }[timing] as ReasonCode
        ];
  const guidance: string[] = [];
  if (classification === 'NOT_ELIGIBLE') {
    guidance.push(
      'Review the official terms and the recorded conditions not met. Completing unknown information alone does not resolve a recorded failed condition.',
    );
  } else {
    if (
      reasons.some((reason) => reason.code === 'purchase_price_unknown') &&
      context.submittedPurchase.purchase_price == null
    )
      guidance.push(
        'You can add the optional purchase price using Edit purchase details, then submit a new check.',
      );
    if (
      reasons.some((reason) =>
        ['purchase_channel_unknown', 'condition_unknown', 'country_unknown'].includes(reason.code),
      )
    )
      guidance.push(
        'The checker has no fields for purchase channel, product condition or country. Review the official terms for these unassessed facts.',
      );
    if (classification === 'ELIGIBLE')
      guidance.push(
        'Check the official terms, claim requirements and official claim site before making a claim.',
      );
    if (classification === 'CLAIM_NOT_YET_OPEN' && promotion.claim_window)
      guidance.push(`Claim period starts on ${calendarDate(promotion.claim_window.opens_on)}.`);
    if (
      classification === 'EXPIRED' ||
      (classification === 'POTENTIALLY_ELIGIBLE' && timing === null)
    )
      guidance.push('Review the official promotion terms for the recorded claim timing.');
  }
  return {
    summary: statuses.find((item) => item.value === classification)!.meaning,
    decisions: reasons.map((reason, index) => ({
      key: String(index),
      text: reasonLabels[reason.code],
    })),
    groups,
    claimTiming,
    evaluatedOn: `As evaluated on ${calendarDate(context.evaluationDate)}.`,
    guidance,
  };
}
