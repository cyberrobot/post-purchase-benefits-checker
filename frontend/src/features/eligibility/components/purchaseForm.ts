import { purchaseRequestSchema, type CheckPurchaseResponse } from '@/lib/api/eligibility.contract';
import { ApiError, safeRequestId } from '@/lib/api/errors';

export const fields = [
  {
    name: 'brand',
    label: 'Manufacturer / Brand',
    help: 'Enter the manufacturer shown on your product',
    type: 'text',
  },
  {
    name: 'model',
    label: 'Product model or SKU',
    help: 'Find the exact model/SKU on the product or receipt',
    type: 'text',
  },
  {
    name: 'retailer',
    label: 'Retailer',
    help: 'Enter the shop or website where you bought it',
    type: 'text',
  },
  {
    name: 'purchase_date',
    label: 'Purchase date',
    help: 'Receipt date, up to today in the UK',
    type: 'date',
  },
] as const;
export type Field = (typeof fields)[number]['name'] | 'purchase_price';
export type Draft = Record<(typeof fields)[number]['name'], string> & { purchase_price?: string };
export type Errors = Partial<Record<Field, string>>;

// This is a form-only product policy. The API accepts every real calendar date.
export function todayInLondon(now = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Europe/London',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(now);
  return ['year', 'month', 'day']
    .map((type) => parts.find((part) => part.type === type)!.value)
    .join('-');
}
export function requestFromDraft(draft: Draft) {
  const { purchase_price, ...required } = draft;
  return {
    ...required,
    ...(purchase_price === undefined || purchase_price === '' ? {} : { purchase_price }),
  };
}
export function validatePurchase(draft: Draft, today = todayInLondon()): Errors {
  const result = purchaseRequestSchema.safeParse(requestFromDraft(draft));
  const errors: Errors = {};
  if (!result.success)
    for (const issue of result.error.issues) {
      if (issue.path[0] === 'purchase_price') {
        errors.purchase_price =
          'Enter a GBP amount such as 799.99, without £ signs or commas (up to 12 whole digits and 2 decimal places)';
        continue;
      }
      const field = fields.find((item) => item.name === issue.path[0]);
      if (!field) continue;
      errors[field.name] =
        field.type === 'date'
          ? 'Enter a valid purchase date'
          : draft[field.name].normalize('NFKC').trim().length === 0
            ? `Enter the ${field.label.toLowerCase()}`
            : draft[field.name].length > 255
              ? 'Use 255 characters or fewer'
              : 'Remove unsupported control characters';
    }
  if (!errors.purchase_date && draft.purchase_date > today)
    errors.purchase_date = 'Purchase date must be today or earlier (UK date)';
  return errors;
}

const classifications = {
  ELIGIBLE: 'meets recorded eligibility rules; this is not an approved or paid claim',
  POTENTIALLY_ELIGIBLE: 'may qualify; more evidence or information could be required',
  NOT_ELIGIBLE: 'does not meet recorded rules',
  CLAIM_NOT_YET_OPEN: 'claim period has not opened',
  EXPIRED: 'claim period has expired',
} as const;
export function completion(data: CheckPurchaseResponse): string[] {
  if (data.outcome === 'unresolved_identity') {
    const label = fields
      .find((field) => field.name === data.unresolved_identity.field)!
      .label.toLowerCase();
    return [
      data.unresolved_identity.status === 'ambiguous'
        ? `More than one ${label} matched. Enter a more specific ${label}, then try again.`
        : `The ${label} could not be found. Check the ${label}, then try again.`,
    ];
  }
  if (!data.promotions.length)
    return ['No matching published promotion was found for these purchase details.'];
  return Object.entries(classifications).flatMap(([classification, description]) => {
    const count = data.promotions.filter(
      (promotion) => promotion.eligibility.classification === classification,
    ).length;
    return count ? [`${count} promotion${count === 1 ? '' : 's'}: ${description}.`] : [];
  });
}
export function failure(error: unknown): string {
  let message = 'The checker encountered a service problem. Please try again.';
  if (!(error instanceof ApiError)) return message;
  switch (error.kind) {
    case 'validation':
      message =
        'The checker could not accept these details. Check the purchase details against your receipt, then try again.';
      break;
    case 'rate_limited': {
      const seconds = error.retryAfterSeconds;
      if (seconds === undefined || !Number.isFinite(seconds) || seconds < 0 || seconds > 86400) {
        message = 'Too many checks. Please wait before trying again.';
        break;
      }
      const wait =
        seconds < 60
          ? `${Math.ceil(seconds)} seconds`
          : seconds < 3600
            ? `${Math.ceil(seconds / 60)} minutes`
            : `${Math.ceil(seconds / 3600)} hours`;
      message = `Too many checks. Please wait ${wait} before trying again.`;
      break;
    }
    case 'timeout':
      message = 'The check took too long and is incomplete. Please try again.';
      break;
    case 'cancelled':
      message = 'The check was cancelled and is incomplete. You can try again.';
      break;
    case 'unavailable':
      message = 'The checker is temporarily unavailable. Please try again later.';
      break;
    case 'server':
    case 'contract':
      break;
  }
  const reference = safeRequestId(error.requestId ?? null);
  return reference ? `${message} Support reference: ${reference}.` : message;
}
