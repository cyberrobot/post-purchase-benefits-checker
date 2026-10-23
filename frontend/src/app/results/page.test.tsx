import { render, screen } from '@testing-library/react';
import ResultsPage from './page';
import { PurchaseCheckSessionProvider } from '@/features/eligibility/session/PurchaseCheckSession';
it('owns one server main and h1 and renders a direct-entry state without API configuration', () => {
  render(
    <PurchaseCheckSessionProvider>
      <ResultsPage />
    </PurchaseCheckSessionProvider>,
  );
  expect(screen.getAllByRole('main')).toHaveLength(1);
  expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content');
  expect(screen.getByRole('main')).toHaveAttribute('tabindex', '-1');
  expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
  expect(screen.getByRole('heading', { name: 'No results in this tab' })).toBeVisible();
  expect(screen.getByRole('link', { name: 'Start a purchase check' })).toHaveAttribute(
    'href',
    '/check',
  );
});
