import { render, screen, waitFor, within } from '@testing-library/react';
import { recordedTerms } from '@/lib/api/promotion-details.fixture';
import { PromotionDetailsView } from './PromotionDetailsView';

it('presents benefit definitions, model amounts, static dates and claim requirements', () => {
  render(<PromotionDetailsView promotion={recordedTerms} />);
  const variants = screen.getAllByRole('region');
  expect(variants).toHaveLength(2);
  variants.forEach((variant, index) => {
    expect(within(variant).getByRole('link', { name: 'Prepare claim checklist' })).toHaveAttribute(
      'href',
      '/promotions/' +
        recordedTerms.public_slug +
        '/claim?variant=' +
        recordedTerms.variants[index].promotion_variant_id,
    );
  });
  expect(variants[0]).toHaveAttribute(
    'id',
    'variant-' + recordedTerms.variants[0].promotion_variant_id,
  );
  expect(within(variants[0]).getByText('£10.00 cashback')).toBeVisible();
  expect(
    within(variants[0]).getByText('5.25% cashback (subject to qualifying purchase price)'),
  ).toBeVisible();
  expect(within(variants[0]).getByText('Warranty extension')).toBeVisible();
  expect(within(variants[0]).getByText('Bonus accessory')).toBeVisible();
  expect(within(variants[0]).getByText('Keep your receipt.')).toBeVisible();
  expect(variants[1]).toHaveTextContent('Other Television: £40.00 cashback');
  expect(variants[1]).toHaveTextContent('Cashback amount not recorded');
  expect(variants[1]).toHaveTextContent('No claim requirements recorded here');
  expect(variants[1]).toHaveTextContent('No retailer restriction recorded');
  expect(screen.getByText(/At least 14 days after purchase/)).toBeVisible();
  expect(screen.getByText('Verification not recorded')).toBeVisible();
  for (const link of screen.getAllByRole('link', { name: /opens in a new tab/ })) {
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  }
});

it('shows relative days and unspecified timing without creating an individual deadline', () => {
  const { rerender } = render(
    <PromotionDetailsView
      promotion={{
        ...recordedTerms,
        claim_window: {
          kind: 'relative',
          opens_after_purchase_days: 14,
          deadline_after_purchase_days: 45,
        },
      }}
    />,
  );
  expect(screen.getByText('Opens 14 calendar days after purchase.')).toBeVisible();
  expect(screen.getByText('Deadline 45 calendar days after purchase.')).toBeVisible();
  expect(screen.queryByText(/claim period open|you qualify/i)).not.toBeInTheDocument();
  rerender(<PromotionDetailsView promotion={{ ...recordedTerms, claim_window: null }} />);
  expect(screen.getByText('Claim timing not recorded. Check the official terms.')).toBeVisible();
});

it('moves keyboard focus to the variant selected by the URL fragment', async () => {
  const id = 'variant-' + recordedTerms.variants[0].promotion_variant_id;
  window.history.replaceState(null, '', '#' + id);
  render(<PromotionDetailsView promotion={recordedTerms} />);
  await waitFor(() => expect(document.getElementById(id)).toHaveFocus());
});
