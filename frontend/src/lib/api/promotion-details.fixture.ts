import type { PromotionDetails } from './promotion-details.contract';

export const id = (value: number) => '00000000-0000-0000-0000-' + String(value).padStart(12, '0');
const stamp = '2026-10-01T10:30:00Z';
const verified = '2026-10-02T11:15:00Z';

export const recordedTerms: PromotionDetails = {
  promotion_id: id(4),
  public_slug: 'example--populated-promotion',
  name: 'Example populated promotion',
  status: 'active',
  manufacturer: { id: id(1), name: 'Example Manufacturer', slug: 'example' },
  purchase_window: { starts_on: '2026-09-01', ends_on: null },
  claim_window: {
    kind: 'fixed',
    opens_on: '2026-10-01',
    deadline_on: '2026-11-30',
    minimum_days_after_purchase: 14,
  },
  variants: [
    {
      promotion_variant_id: id(5),
      code: 'base',
      name: 'Base offer',
      retailer: { id: id(2), name: 'Example Retailer' },
      products: [{ id: id(3), name: 'Example Television', model_number: 'TV-100' }],
      benefits: [
        {
          benefit_id: id(6),
          benefit_type: 'cashback',
          name: 'Fixed cashback',
          description: null,
          reward: { kind: 'fixed_amount', amount_gbp: '10.00' },
        },
        {
          benefit_id: id(16),
          benefit_type: 'cashback',
          name: 'Price-based cashback',
          description: 'Qualifying purchase price applies.',
          reward: { kind: 'percentage', percentage: '5.25' },
        },
        {
          benefit_id: id(17),
          benefit_type: 'extended_warranty',
          name: 'Warranty extension',
          description: 'Review the warranty conditions.',
          reward: null,
        },
        {
          benefit_id: id(18),
          benefit_type: 'free_gift',
          name: 'Bonus accessory',
          description: null,
          reward: null,
        },
      ],
      requirements: [
        { requirement_id: id(19), requirement_type: 'receipt', description: 'Keep your receipt.' },
      ],
    },
    {
      promotion_variant_id: id(25),
      code: 'special',
      name: null,
      retailer: null,
      products: [
        { id: id(3), name: 'Example Television', model_number: 'TV-100' },
        { id: id(33), name: 'Other Television', model_number: null },
      ],
      benefits: [
        {
          benefit_id: id(26),
          benefit_type: 'cashback',
          name: 'Model cashback',
          description: null,
          reward: {
            kind: 'product_specific',
            values: [
              { product_id: id(3), amount_gbp: '12.00' },
              { product_id: id(33), amount_gbp: '40.00' },
            ],
          },
        },
        {
          benefit_id: id(27),
          benefit_type: 'cashback',
          name: 'Other cashback',
          description: null,
          reward: null,
        },
      ],
      requirements: [],
    },
  ],
  provenance: {
    official_source_url: 'https://example.com/offer',
    claim_url: 'https://example.com/claim',
    last_verified_at: verified,
  },
  sources: [
    {
      source_id: id(8),
      role: 'claim',
      url: 'https://example.com/claim',
      source_type: 'web_page',
      retrieved_at: stamp,
      verified_at: verified,
    },
    {
      source_id: id(7),
      role: 'primary',
      url: 'https://example.com/offer',
      source_type: 'web_page',
      retrieved_at: stamp,
      verified_at: verified,
    },
    {
      source_id: id(9),
      role: 'supporting',
      url: 'https://example.com/support',
      source_type: 'other',
      retrieved_at: stamp,
      verified_at: null,
    },
    {
      source_id: id(10),
      role: 'terms',
      url: 'https://example.com/terms.pdf',
      source_type: 'pdf',
      retrieved_at: stamp,
      verified_at: verified,
    },
  ],
};
