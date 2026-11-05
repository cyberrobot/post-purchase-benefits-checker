import { fireEvent, render, screen, within } from '@testing-library/react';
import { populatedClaim } from '@/lib/api/promotion.fixture';
import { resolved as rawResolved, unresolved as rawUnresolved } from '@/lib/api/fixtures';
import {
  checkPurchaseResponseSchema,
  type CheckPurchaseResponse,
} from '@/lib/api/eligibility.contract';
import {
  PurchaseCheckSessionProvider,
  usePurchaseCheckSession,
} from '../session/PurchaseCheckSession';
import { ResultsOverview } from './ResultsOverview';
import { statuses } from './presentation';
const resolved = checkPurchaseResponseSchema.parse(rawResolved);
const unresolved = checkPurchaseResponseSchema.parse(rawUnresolved);
const promotion = populatedClaim.outcome === 'resolved' ? populatedClaim.promotions[0] : null;
const purchase = {
  brand: 'My Brand',
  model: '<script>alert(1)</script>',
  retailer: 'My Shop',
  purchase_date: '2024-02-29',
  purchase_price: '999999999999.99',
};
function show(response: CheckPurchaseResponse) {
  function Setup() {
    const session = usePurchaseCheckSession();
    return (
      <>
        <button onClick={() => session.publish(purchase, response)}>Load</button>
        <ResultsOverview />
      </>
    );
  }
  render(
    <PurchaseCheckSessionProvider>
      <Setup />
    </PurchaseCheckSessionProvider>,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Load' }));
}
it('shows the exact purchase, all benefits, source verification and functional safe disclosures', () => {
  show(populatedClaim);
  expect(
    screen.getByRole('heading', { name: `${purchase.brand} · ${purchase.model}` }),
  ).toBeVisible();
  expect(screen.getByText('£999,999,999,999.99')).toBeVisible();
  expect(screen.getByText('29 Feb 2024')).toBeVisible();
  expect(screen.getByText('08 Oct 2026')).toBeVisible();
  const summary = screen.getByRole('region', { name: 'Checked purchase summary' });
  expect(summary).toHaveClass('wrap-anywhere');
  expect(within(summary).getByText('My Shop')).toHaveClass('wrap-anywhere');
  expect(within(summary).getByRole('link', { name: /Edit purchase details/ })).toHaveClass(
    'text-brand',
  );
  const card = screen.getByRole('article');
  expect(within(card).getByRole('heading', { name: '£10.00 cashback' })).toBeVisible();
  expect(within(card).getByRole('heading', { name: 'Percentage cashback' })).toBeVisible();
  expect(
    within(card).getByText('Provide the purchase price to calculate the cashback reward.'),
  ).toBeVisible();
  expect(within(card).getByText('02 Oct 2026').parentElement).toHaveTextContent('My Brand');
  const detailsButton = within(card).getByRole('button', { name: 'View Full Promotion Details' });
  expect(detailsButton).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(detailsButton);
  expect(within(card).getByText(/not an approved or paid claim/)).toBeVisible();
  expect(within(card).getByText(/Claim window opens/)).toHaveTextContent('01 Oct 2026');
  expect(within(card).getByText('Recorded rules').closest('details')).not.toHaveAttribute('open');
  for (const link of within(card).getAllByRole('link')) {
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener noreferrer'));
  }
  expect(document.querySelector('script')).toBeNull();
});
it('keeps six variants, five classifications and local zero-count filters with no status inference', () => {
  if (populatedClaim.outcome !== 'resolved') throw new Error('fixture');
  const promotions = [...statuses, statuses[4]].map((s, i) => ({
    ...promotion!,
    promotion_variant_id: `variant-${i}`,
    variant_name: `Variant ${i}`,
    eligibility: {
      ...promotion!.eligibility,
      classification: s.value,
      claim_window_status: null,
    },
  }));
  show({ ...populatedClaim, promotions });
  expect(screen.getAllByRole('article')).toHaveLength(6);
  expect(screen.getByRole('button', { name: 'Not eligible (2)' })).toHaveAttribute(
    'aria-pressed',
    'false',
  );
  fireEvent.click(screen.getByRole('button', { name: 'Not eligible (2)' }));
  expect(screen.getAllByRole('article')).toHaveLength(2);
  expect(screen.getByRole('status')).toHaveTextContent('Showing 2 of 6');
  expect(screen.queryByText(/Recorded claim timing: Claim period open/)).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'All (6)' })).toBeVisible();
});
it('renders null and empty details honestly and zero filtered state can reset', () => {
  if (populatedClaim.outcome !== 'resolved') throw new Error('fixture');
  show({
    ...populatedClaim,
    promotions: [
      {
        ...promotion!,
        benefits: [],
        requirements: [],
        explanation: [],
        claim_window: null,
        eligibility: {
          ...promotion!.eligibility,
          claim_window_status: null,
          rule_evaluations: [],
          reasons: [],
        },
      },
    ],
  });
  expect(screen.getByText('No benefit details supplied.')).toBeVisible();
  expect(screen.getByText('No explanation supplied.')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'View Full Promotion Details' }));
  expect(screen.getByText(/The response lists no requirements/)).toBeVisible();
  expect(screen.queryByText(/Claim opens/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Not eligible (0)' }));
  expect(screen.getByRole('heading', { name: 'No results in this category' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Show all results' }));
  expect(screen.getAllByRole('article')).toHaveLength(1);
});
it.each(['not_found', 'ambiguous'] as const)(
  'shows field-specific %s guidance without candidate IDs',
  (status) => {
    if (unresolved.outcome !== 'unresolved_identity') throw new Error('fixture');
    show({
      ...unresolved,
      unresolved_identity: { field: 'model', status, candidate_ids: ['secret-id'] },
    });
    expect(screen.getByRole('heading', { name: 'Check your product model or SKU' })).toBeVisible();
    expect(
      screen.getByText(
        status === 'ambiguous'
          ? /More than one product model or sku matched/
          : /product model or sku could not be found/,
      ),
    ).toBeVisible();
    expect(screen.queryByText(/secret-id/)).not.toBeInTheDocument();
    expect(screen.queryByRole('article')).not.toBeInTheDocument();
  },
);
it('distinguishes published no-match from missing tab state', () => {
  show(resolved);
  expect(screen.getByRole('heading', { name: 'No matching published promotions' })).toBeVisible();
  expect(screen.queryByText('No results in this tab')).not.toBeInTheDocument();
});
it('wraps escaped long content and preserves non-cash benefits and unavailable reward reasons', () => {
  if (populatedClaim.outcome !== 'resolved' || !promotion) throw new Error('fixture');
  const longName = '<img src=x onerror=alert(1)>'.repeat(30);
  show({
    ...populatedClaim,
    promotions: [
      {
        ...promotion,
        promotion_name: longName,
        variant_name: 'Warranty variant',
        benefits: [
          {
            ...promotion.benefits[0],
            benefit_type: 'extended_warranty',
            name: 'Recorded extended cover',
            description: longName,
            cashback_reward_gbp: null,
            reward_unavailable_reason: 'reward_not_configured',
            reward_unavailable_explanation: null,
          },
          {
            ...promotion.benefits[0],
            benefit_id: 'second-benefit',
            benefit_type: 'free_gift',
            name: 'Recorded gift',
            cashback_reward_gbp: null,
            reward_unavailable_reason: null,
            reward_unavailable_explanation: null,
          },
        ],
        claim_window: null,
        eligibility: { ...promotion.eligibility, claim_window_status: null },
      },
    ],
  });
  expect(screen.getByRole('heading', { name: longName })).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Recorded extended cover' })).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Recorded gift' })).toBeVisible();
  expect(screen.queryByText('reward not configured')).not.toBeInTheDocument();
  expect(screen.queryByText('No monetary reward amount supplied.')).not.toBeInTheDocument();
  expect(document.querySelector('img')).toBeNull();
  expect(screen.queryByText(/£150|5-Year|Claim period open/)).not.toBeInTheDocument();
});

it('shows unavailable monetary reward wording for cashback without supplied details', () => {
  if (populatedClaim.outcome !== 'resolved' || !promotion) throw new Error('fixture');
  show({
    ...populatedClaim,
    promotions: [
      {
        ...promotion,
        benefits: [
          {
            ...promotion.benefits[0],
            cashback_reward_gbp: null,
            reward_unavailable_reason: null,
            reward_unavailable_explanation: null,
          },
        ],
      },
    ],
  });
  expect(screen.getByText('No monetary reward amount supplied.')).toBeVisible();
  expect(screen.queryByRole('heading', { name: '£10.00 cashback' })).not.toBeInTheDocument();
});

it('switches between cards and actual recorded rule rows while preserving filters and missing outcomes', () => {
  if (populatedClaim.outcome !== 'resolved' || !promotion) throw new Error('fixture');
  show({
    ...populatedClaim,
    promotions: [
      promotion,
      {
        ...promotion,
        promotion_variant_id: 'missing-rules',
        variant_name: 'Variant without evaluations',
        eligibility: {
          ...promotion.eligibility,
          rule_evaluations: [],
          classification: 'NOT_ELIGIBLE',
        },
      },
    ],
  });
  const matrix = screen.getByRole('button', { name: 'Rule Matrix' });
  expect(matrix).toHaveAttribute('aria-pressed', 'false');
  fireEvent.click(matrix);
  expect(matrix).toHaveAttribute('aria-pressed', 'true');
  expect(screen.queryByRole('article')).not.toBeInTheDocument();
  const table = screen.getByRole('table', { name: /Recorded rule matrix/ });
  expect(within(table).getAllByRole('row')).toHaveLength(3);
  expect(within(table).getByText('product: satisfied')).toBeVisible();
  expect(within(table).getByText('Not supplied')).toBeVisible();
  expect(within(table).getByText('Variant without evaluations')).toBeVisible();
  for (const rule of promotion.eligibility.rule_evaluations) {
    expect(within(table).getByText(rule.reason_code.replaceAll('_', ' '))).toBeVisible();
  }
  fireEvent.click(screen.getByRole('button', { name: 'Not eligible (1)' }));
  expect(within(table).getAllByRole('row')).toHaveLength(2);
  fireEvent.click(screen.getByRole('button', { name: 'Cards' }));
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
  expect(screen.getAllByRole('article')).toHaveLength(1);
});

it('keeps long supplementary descriptions collapsed and exposes truthful upcoming dates with keyboard controls', () => {
  if (populatedClaim.outcome !== 'resolved' || !promotion) throw new Error('fixture');
  show({
    ...populatedClaim,
    promotions: [
      {
        ...promotion,
        eligibility: {
          ...promotion.eligibility,
          classification: 'CLAIM_NOT_YET_OPEN',
          claim_window_status: 'not_yet_open',
          rule_evaluations: [
            { kind: 'retailer', status: 'satisfied', reason_code: 'retailer_match' },
            { kind: 'purchase_price', status: 'unknown', reason_code: 'purchase_price_unknown' },
            {
              kind: 'purchase_date',
              status: 'not_satisfied',
              reason_code: 'purchase_date_before_start',
            },
          ],
        },
        claim_window: { status: 'not_yet_open', opens_on: '2026-11-27', deadline_on: '2026-12-31' },
        benefits: [
          { ...promotion.benefits[0], description: 'A long supplementary benefit description.' },
        ],
      },
    ],
  });
  const card = screen.getByRole('article');
  expect(within(card).getByText('Claim not yet open')).toBeVisible();
  expect(within(card).getByText('Retailer matches recorded promotion rules')).toBeVisible();
  expect(within(card).getByText('Purchase price could not be evaluated')).toBeVisible();
  expect(
    within(card).getByText('Purchase date is before the recorded promotion starts'),
  ).toBeVisible();
  expect(within(card).getByText('A long supplementary benefit description.')).not.toBeVisible();
  const guide = within(card).getByRole('button', { name: 'Claim Window Guide' });
  fireEvent.click(guide);
  expect(guide).toHaveAttribute('aria-expanded', 'true');
  expect(within(card).getByRole('region', { name: 'Claim window guide' })).toHaveTextContent(
    '27 Nov 2026',
  );
  expect(within(card).getByRole('region', { name: 'Claim window guide' })).toHaveTextContent(
    '31 Dec 2026',
  );
  fireEvent.click(within(card).getByRole('button', { name: 'View Full Promotion Details' }));
  expect(within(card).getByText('A long supplementary benefit description.')).toBeVisible();
  expect(within(card).getByRole('link', { name: /Official Portal Terms/ })).toHaveAttribute(
    'href',
    promotion.provenance.official_source_url,
  );
});
