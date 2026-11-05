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
const reasonStatuses = {
  manufacturer_match: 'satisfied',
  manufacturer_mismatch: 'not_satisfied',
  product_match: 'satisfied',
  product_mismatch: 'not_satisfied',
  retailer_match: 'satisfied',
  retailer_mismatch: 'not_satisfied',
  purchase_channel_match: 'satisfied',
  purchase_channel_mismatch: 'not_satisfied',
  purchase_channel_unknown: 'unknown',
  purchase_date_match: 'satisfied',
  purchase_date_before_start: 'not_satisfied',
  purchase_date_after_end: 'not_satisfied',
  purchase_price_match: 'satisfied',
  purchase_price_below_minimum: 'not_satisfied',
  purchase_price_above_maximum: 'not_satisfied',
  purchase_price_unknown: 'unknown',
  condition_match: 'satisfied',
  condition_mismatch: 'not_satisfied',
  condition_unknown: 'unknown',
  country_match: 'satisfied',
  country_mismatch: 'not_satisfied',
  country_unknown: 'unknown',
} satisfies Record<Rule['reason_code'], Rule['status']>;
function reasonStatus(code: ReasonCode): Rule['status'] | undefined {
  return Object.hasOwn(reasonStatuses, code)
    ? reasonStatuses[code as Rule['reason_code']]
    : undefined;
}
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
  // Match occurrences one for one: a decision reason and its evaluation describe
  // one outcome, while repeated reasons/evaluations remain separate evidence.
  const matchedReasons = new Set<number>();
  const supplementaryRules = rules.flatMap((rule, index) => {
    const match = reasons.findIndex(
      (reason, reasonIndex) =>
        !matchedReasons.has(reasonIndex) &&
        reason.code === rule.reason_code &&
        reason.rule_kind === rule.kind &&
        reasonStatus(reason.code) === rule.status,
    );
    if (match !== -1) {
      matchedReasons.add(match);
      return [];
    }
    return [{ ...rule, index }];
  });
  const groupDefinitions: { heading: string; status: Rule['status'] }[] = [
    { heading: 'Conditions not met', status: 'not_satisfied' },
    { heading: "Information we couldn't assess", status: 'unknown' },
    { heading: 'Recorded checks passed', status: 'satisfied' },
  ];
  const groups = groupDefinitions.map((group) => ({
    ...group,
    decisive: reasons.some((reason) => reasonStatus(reason.code) === group.status),
    items: [
      ...reasons.flatMap((reason, index) =>
        reasonStatus(reason.code) === group.status
          ? [{ key: `reason-${index}`, text: reasonLabels[reason.code], decisive: true }]
          : [],
      ),
      ...supplementaryRules.flatMap((rule) =>
        rule.status === group.status
          ? [{ key: `rule-${rule.index}`, text: reasonLabels[rule.reason_code], decisive: false }]
          : [],
      ),
    ],
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
  }
  if (
    classification === 'POTENTIALLY_ELIGIBLE' &&
    !groups[0].items.length &&
    reasons.some((reason) => reason.code === 'purchase_price_unknown') &&
    context.submittedPurchase.purchase_price == null
  )
    guidance.push(
      'You can add the optional purchase price using Edit purchase details, then submit a new check.',
    );
  const unsupportedFacts = {
    purchase_channel_unknown: 'purchase channel',
    condition_unknown: 'product condition',
    country_unknown: 'purchase country',
  };
  for (const code of new Set(reasons.map((reason) => reason.code))) {
    if (Object.hasOwn(unsupportedFacts, code)) {
      const fact = unsupportedFacts[code as keyof typeof unsupportedFacts];
      guidance.push(
        `The checker currently has no field for ${fact}. Review the official terms for this unassessed fact.`,
      );
    }
  }
  if (classification !== 'NOT_ELIGIBLE') {
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
      grouped: reasonStatus(reason.code) !== undefined,
    })),
    groups,
    claimTiming,
    evaluatedOn: `As evaluated on ${calendarDate(context.evaluationDate)}.`,
    guidance,
  };
}
