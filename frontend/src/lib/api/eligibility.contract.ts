import { z } from 'zod';

// Wire schemas mirror backend/app/api/schemas/eligibility.py; no eligibility rules.
export const calendarDateSchema = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/)
  .refine((value) => {
    const [year, month, day] = value.split('-').map(Number);
    if (year < 1 || month < 1 || month > 12) return false;
    const days = [
      31,
      year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28,
      31,
      30,
      31,
      30,
      31,
      31,
      30,
      31,
      30,
      31,
    ];
    return day >= 1 && day <= days[month - 1];
  });
const identityText = z
  .string()
  .max(255)
  .refine(
    (value) => value.normalize('NFKC').trim().length > 0 && !/[\x00-\x08\x0e-\x1f\x7f]/.test(value),
  );
export const purchaseRequestSchema = z
  .object({
    brand: identityText,
    model: identityText,
    retailer: identityText,
    purchase_date: calendarDateSchema,
    purchase_price: z
      .string()
      .regex(/^(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?$/)
      .nullable()
      .optional(),
  })
  .strict();
const uuid = z.string().regex(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
const timestamp = z.string().datetime({ offset: true });
const ruleKind = z.enum([
  'manufacturer',
  'product',
  'retailer',
  'purchase_channel',
  'purchase_date',
  'purchase_price',
  'condition',
  'country',
]);
const ruleReason = z.enum([
  'manufacturer_match',
  'manufacturer_mismatch',
  'product_match',
  'product_mismatch',
  'retailer_match',
  'retailer_mismatch',
  'purchase_channel_match',
  'purchase_channel_mismatch',
  'purchase_channel_unknown',
  'purchase_date_match',
  'purchase_date_before_start',
  'purchase_date_after_end',
  'purchase_price_match',
  'purchase_price_below_minimum',
  'purchase_price_above_maximum',
  'purchase_price_unknown',
  'condition_match',
  'condition_mismatch',
  'condition_unknown',
  'country_match',
  'country_mismatch',
  'country_unknown',
]);
const reasonCode = z.enum([
  'manufacturer_match',
  'manufacturer_mismatch',
  'product_match',
  'product_mismatch',
  'retailer_match',
  'retailer_mismatch',
  'purchase_channel_match',
  'purchase_channel_mismatch',
  'purchase_channel_unknown',
  'purchase_date_match',
  'purchase_date_before_start',
  'purchase_date_after_end',
  'purchase_price_match',
  'purchase_price_below_minimum',
  'purchase_price_above_maximum',
  'purchase_price_unknown',
  'condition_match',
  'condition_mismatch',
  'condition_unknown',
  'country_match',
  'country_mismatch',
  'country_unknown',
  'all_configured_rules_satisfied',
  'claim_window_open',
  'claim_window_not_yet_open',
  'claim_window_expired',
  'claim_window_unspecified',
]);
const claimStatus = z.enum(['open', 'not_yet_open', 'expired']);
const sourceType = z.enum(['web_page', 'pdf', 'other']);
export const promotionSchema = z.object({
  promotion_id: uuid,
  promotion_variant_id: uuid,
  promotion_name: z.string(),
  variant_name: z.string().nullable(),
  promotion_status: z.enum(['discovered', 'extracted', 'review', 'active', 'expired', 'archived']),
  eligibility: z.object({
    classification: z.enum([
      'ELIGIBLE',
      'POTENTIALLY_ELIGIBLE',
      'NOT_ELIGIBLE',
      'CLAIM_NOT_YET_OPEN',
      'EXPIRED',
    ]),
    reasons: z.array(z.object({ code: reasonCode, rule_kind: ruleKind.nullable() })),
    rule_evaluations: z.array(
      z.object({
        kind: ruleKind,
        status: z.enum(['satisfied', 'not_satisfied', 'unknown']),
        reason_code: ruleReason,
      }),
    ),
    claim_window_status: claimStatus.nullable(),
  }),
  claim_window: z
    .object({ status: claimStatus, opens_on: calendarDateSchema, deadline_on: calendarDateSchema })
    .nullable(),
  benefits: z.array(
    z.object({
      benefit_id: uuid,
      benefit_type: z.enum(['cashback', 'extended_warranty', 'free_gift']),
      name: z.string(),
      description: z.string().nullable(),
      cashback_reward_gbp: z
        .string()
        .regex(/^\d+(?:\.\d+)?$/)
        .nullable(),
      reward_unavailable_reason: z
        .enum(['purchase_price_required_for_reward', 'reward_not_configured'])
        .nullable(),
      reward_unavailable_explanation: z.string().nullable(),
    }),
  ),
  requirements: z.array(
    z.object({
      requirement_type: z.enum([
        'receipt',
        'serial_number',
        'registration',
        'invoice',
        'barcode',
        'imei',
        'installation_evidence',
      ]),
      description: z.string().nullable(),
    }),
  ),
  last_verified_at: timestamp,
  provenance: z.object({
    official_source_url: z.string(),
    source_type: sourceType,
    retrieved_at: timestamp,
    verified_at: timestamp,
    claim_url: z.string(),
  }),
  sources: z.array(
    z.object({
      source_id: uuid,
      role: z.enum(['primary', 'terms', 'claim', 'supporting']),
      url: z.string(),
      source_type: sourceType,
      retrieved_at: timestamp,
      verified_at: timestamp.nullable(),
    }),
  ),
  explanation: z.array(z.string()),
});
export const checkPurchaseResponseSchema = z.discriminatedUnion('outcome', [
  z.object({
    outcome: z.literal('resolved'),
    evaluation_date: calendarDateSchema,
    resolved_identity: z.object({ manufacturer_id: uuid, retailer_id: uuid, product_id: uuid }),
    promotions: z.array(promotionSchema),
    no_match_reason: z.literal('no_matching_published_promotions').nullable(),
    explanation: z.array(z.string()),
  }),
  z.object({
    outcome: z.literal('unresolved_identity'),
    evaluation_date: calendarDateSchema,
    unresolved_identity: z.object({
      field: z.enum(['brand', 'model', 'retailer']),
      status: z.enum(['not_found', 'ambiguous']),
      candidate_ids: z.array(uuid),
    }),
    explanation: z.array(z.string()),
  }),
]);
export const problemSchema = z.object({
  type: z.string().max(512),
  title: z.string().max(256),
  status: z.number().int().min(400).max(599),
  detail: z.string().max(1024),
  code: z.string().regex(/^[a-z][a-z0-9_]{0,79}$/),
  request_id: uuid,
});
export type PurchaseRequest = z.infer<typeof purchaseRequestSchema>;
export type CheckPurchaseResponse = z.infer<typeof checkPurchaseResponseSchema>;
export type Problem = z.infer<typeof problemSchema>;
