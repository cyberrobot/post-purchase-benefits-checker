import { PurchaseCheckSessionProvider } from '@/features/eligibility/session/PurchaseCheckSession';
import { render, screen } from '@testing-library/react';
import CheckPurchasePage from './page';
import { QueryProvider } from '@/components/providers/QueryProvider';
it('renders the server page with one main, one heading and the shared form without API configuration', () => {
  render(
    <QueryProvider>
      <PurchaseCheckSessionProvider>
        <CheckPurchasePage />
      </PurchaseCheckSessionProvider>
    </QueryProvider>,
  );
  expect(screen.getAllByRole('main')).toHaveLength(1);
  expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content');
  expect(screen.getByRole('main')).toHaveAttribute('tabindex', '-1');
  expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Check your purchase');
  expect(screen.getByRole('form', { name: 'Check a purchase' })).toBeVisible();
  expect(screen.getByLabelText('Manufacturer / Brand')).toBeRequired();
});
