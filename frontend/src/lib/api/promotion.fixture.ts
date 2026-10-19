import type { CheckPurchaseResponse } from './eligibility.contract';
export const populated = {
  outcome: 'resolved',
  evaluation_date: '2026-10-08',
  resolved_identity: {
    manufacturer_id: '00000000-0000-0000-0000-000000000001',
    retailer_id: '00000000-0000-0000-0000-000000000002',
    product_id: '00000000-0000-0000-0000-000000000003',
  },
  promotions: [
    {
      promotion_id: '00000000-0000-0000-0000-000000000004',
      promotion_variant_id: '00000000-0000-0000-0000-000000000005',
      promotion_name: 'Example cashback',
      variant_name: null,
      promotion_status: 'active',
      eligibility: {
        classification: 'POTENTIALLY_ELIGIBLE',
        reasons: [
          {
            code: 'all_configured_rules_satisfied',
            rule_kind: null,
          },
          {
            code: 'claim_window_unspecified',
            rule_kind: null,
          },
        ],
        rule_evaluations: [
          {
            kind: 'product',
            status: 'satisfied',
            reason_code: 'product_match',
          },
        ],
        claim_window_status: null,
      },
      claim_window: null,
      benefits: [
        {
          benefit_id: '00000000-0000-0000-0000-000000000006',
          benefit_type: 'cashback',
          name: 'Cashback',
          description: null,
          cashback_reward_gbp: '10',
          reward_unavailable_reason: null,
          reward_unavailable_explanation: null,
        },
      ],
      requirements: [],
      last_verified_at: '2026-10-02T00:00:00Z',
      provenance: {
        official_source_url: 'https://example.com/offer',
        source_type: 'web_page',
        retrieved_at: '2026-10-01T00:00:00Z',
        verified_at: '2026-10-02T00:00:00Z',
        claim_url: 'https://example.com/claim',
      },
      sources: [
        {
          source_id: '00000000-0000-0000-0000-000000000007',
          role: 'primary',
          url: 'https://example.com/offer',
          source_type: 'web_page',
          retrieved_at: '2026-10-01T00:00:00Z',
          verified_at: '2026-10-02T00:00:00Z',
        },
        {
          source_id: '00000000-0000-0000-0000-000000000008',
          role: 'claim',
          url: 'https://example.com/claim',
          source_type: 'web_page',
          retrieved_at: '2026-10-01T00:00:00Z',
          verified_at: '2026-10-03T00:00:00Z',
        },
      ],
      explanation: [
        'The recorded eligibility rules match this purchase.',
        'The claim period is not available.',
      ],
    },
  ],
  no_match_reason: null,
  explanation: [],
};

// Backend-compatible claim details and a percentage reward awaiting a purchase price.
export const populatedClaim: CheckPurchaseResponse = {
  ...populated,
  outcome: 'resolved',
  promotions: [
    {
      ...populated.promotions[0],
      promotion_status: 'active',
      eligibility: {
        classification: 'ELIGIBLE',
        reasons: [
          { code: 'all_configured_rules_satisfied', rule_kind: null },
          { code: 'claim_window_open', rule_kind: null },
        ],
        rule_evaluations: [{ kind: 'product', status: 'satisfied', reason_code: 'product_match' }],
        claim_window_status: 'open',
      },
      claim_window: { status: 'open', opens_on: '2026-10-01', deadline_on: '2026-11-30' },
      benefits: [
        {
          ...populated.promotions[0].benefits[0],
          benefit_type: 'cashback',
          cashback_reward_gbp: '10.00',
        },
        {
          benefit_id: '00000000-0000-0000-0000-000000000009',
          benefit_type: 'cashback',
          name: 'Percentage cashback',
          description: 'A percentage of the purchase price.',
          cashback_reward_gbp: null,
          reward_unavailable_reason: 'purchase_price_required_for_reward',
          reward_unavailable_explanation:
            'Provide the purchase price to calculate the cashback reward.',
        },
      ],
      requirements: [
        { requirement_type: 'receipt', description: 'Upload a dated proof of purchase.' },
        { requirement_type: 'serial_number', description: null },
      ],
      provenance: { ...populated.promotions[0].provenance, source_type: 'web_page' },
      sources: populated.promotions[0].sources.map((source) => ({
        ...source,
        role: source.role as 'primary' | 'claim',
        source_type: 'web_page',
      })),
      explanation: [
        'The recorded eligibility rules match this purchase.',
        'The claim period is open.',
      ],
    },
  ],
};
