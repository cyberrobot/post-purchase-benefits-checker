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
  const card = screen.getByRole('article');
  expect(within(card).getByRole('heading', { name: '£10.00 cashback' })).toBeVisible();
  expect(within(card).getByRole('heading', { name: 'Percentage cashback' })).toBeVisible();
  expect(
    within(card).getByText('Provide the purchase price to calculate the cashback reward.'),
  ).toBeVisible();
  expect(within(card).getByText(/Source last verified/)).toHaveTextContent('2 Oct 2026');
  expect(within(card).getByText(/not an approved or paid claim/)).toBeVisible();
  expect(within(card).getByText('Claim period open', { exact: false })).toBeVisible();
  expect(within(card).getByText('View claim requirements').closest('details')).not.toHaveAttribute(
    'open',
  );
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
  expect(screen.getByText(/The response lists no requirements/)).toBeInTheDocument();
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
  expect(screen.getByText('reward not configured')).toBeVisible();
  expect(document.querySelector('img')).toBeNull();
  expect(screen.queryByText(/£150|5-Year|Claim period open/)).not.toBeInTheDocument();
});
