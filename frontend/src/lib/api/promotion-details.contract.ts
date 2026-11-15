import { z } from 'zod';
import { httpSourceUrlSchema, timestamp, uuid } from './eligibility.contract';
import { isPromotionSlugComponent, publicSlugSchema } from './promotion-slug';

const name = z.string().min(1);
const date = z.iso.date();
const decimal = z
  .string()
  .regex(/^[0-9]+(?:\.[0-9]+)?$/)
  .refine((value) => !/\s/.test(value));
const amount = decimal.refine(
  (value) => /[1-9]/.test(value) && (value.split('.')[1]?.length ?? 0) <= 2,
);
const percentage = decimal.refine(
  (value) => Number(value) > 0 && Number(value) <= 100 && (value.split('.')[1]?.length ?? 0) <= 4,
);
const days = z.number().int().min(0).max(2147483647);
const identity = z.strictObject({ id: uuid, name });
const product = identity.extend({ model_number: z.string().nullable() });
const reward = z.discriminatedUnion('kind', [
  z.strictObject({ kind: z.literal('fixed_amount'), amount_gbp: amount }),
  z.strictObject({ kind: z.literal('percentage'), percentage }),
  z.strictObject({
    kind: z.literal('product_specific'),
    values: z.array(z.strictObject({ product_id: uuid, amount_gbp: amount })).min(1),
  }),
]);
const variant = z.strictObject({
  promotion_variant_id: uuid,
  code: name,
  name: z.string().nullable(),
  retailer: identity.nullable(),
  products: z.array(product).min(1),
  benefits: z
    .array(
      z.strictObject({
        benefit_id: uuid,
        benefit_type: z.enum(['cashback', 'extended_warranty', 'free_gift']),
        name,
        description: z.string().nullable(),
        reward: reward.nullable(),
      }),
    )
    .min(1),
  requirements: z.array(
    z.strictObject({
      requirement_id: uuid,
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
});
const source = z.strictObject({
  source_id: uuid,
  role: z.enum(['primary', 'terms', 'claim', 'supporting']),
  url: httpSourceUrlSchema,
  source_type: z.enum(['web_page', 'pdf', 'other']),
  retrieved_at: timestamp,
  verified_at: timestamp.nullable(),
});
const unique = (values: string[]) =>
  new Set(values.map((value) => value.toLowerCase())).size === values.length;

export const promotionDetailsSchema = z
  .strictObject({
    promotion_id: uuid,
    public_slug: publicSlugSchema,
    name,
    status: z.enum(['active', 'expired']),
    manufacturer: identity.extend({ slug: z.string().refine(isPromotionSlugComponent) }),
    purchase_window: z.strictObject({ starts_on: date.nullable(), ends_on: date.nullable() }),
    claim_window: z
      .discriminatedUnion('kind', [
        z.strictObject({
          kind: z.literal('fixed'),
          opens_on: date,
          deadline_on: date,
          minimum_days_after_purchase: days.nullable(),
        }),
        z.strictObject({
          kind: z.literal('relative'),
          opens_after_purchase_days: days,
          deadline_after_purchase_days: days,
        }),
      ])
      .nullable(),
    variants: z.array(variant).min(1),
    provenance: z.strictObject({
      official_source_url: httpSourceUrlSchema,
      claim_url: httpSourceUrlSchema,
      last_verified_at: timestamp,
    }),
    sources: z.array(source).min(2),
  })
  .refine((data) => {
    const primary = data.sources.filter((item) => item.role === 'primary');
    const claim = data.sources.filter((item) => item.role === 'claim');
    if (
      primary.length !== 1 ||
      claim.length !== 1 ||
      !claim[0].verified_at ||
      primary[0].url !== data.provenance.official_source_url ||
      claim[0].url !== data.provenance.claim_url ||
      primary[0].verified_at !== data.provenance.last_verified_at
    )
      return false;

    const { starts_on: start, ends_on: end } = data.purchase_window;
    const window = data.claim_window;
    return (
      data.public_slug.startsWith(data.manufacturer.slug + '--') &&
      !(start && end && start > end) &&
      !(window?.kind === 'fixed' && window.opens_on > window.deadline_on) &&
      !(
        window?.kind === 'relative' &&
        window.opens_after_purchase_days > window.deadline_after_purchase_days
      ) &&
      unique(data.sources.map((item) => item.source_id)) &&
      data.sources.every(
        (item) =>
          !item.verified_at || Date.parse(item.verified_at) >= Date.parse(item.retrieved_at),
      ) &&
      unique(data.variants.map((item) => item.promotion_variant_id)) &&
      new Set(data.variants.map((item) => item.code)).size === data.variants.length &&
      data.variants.every(({ products, benefits, requirements }) => {
        const ids = new Set(products.map((item) => item.id));
        return (
          ids.size === products.length &&
          unique(benefits.map((item) => item.benefit_id)) &&
          unique(requirements.map((item) => item.requirement_id)) &&
          benefits.every(({ benefit_type: type, reward }) => {
            if (!reward) return true;
            if (type !== 'cashback') return false;
            if (reward.kind !== 'product_specific') return true;
            const values = reward.values.map((item) => item.product_id);
            return (
              values.length === ids.size && unique(values) && values.every((id) => ids.has(id))
            );
          })
        );
      })
    );
  }, 'Inconsistent published promotion');

export type PromotionDetails = z.infer<typeof promotionDetailsSchema>;
