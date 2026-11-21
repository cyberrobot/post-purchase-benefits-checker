import { PurchaseCheckSessionProvider } from '@/features/eligibility/session/PurchaseCheckSession';
import { fireEvent, render, screen, within } from '@testing-library/react';
import Home from '@/app/page';
import { QueryProvider } from '@/components/providers/QueryProvider';

it('introduces purchase checking with the actual four-field entry form', () => {
  render(
    <QueryProvider>
      <PurchaseCheckSessionProvider>
        <Home />
      </PurchaseCheckSessionProvider>
    </QueryProvider>,
  );
  const main = screen.getByRole('main');
  expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
  expect(within(main).getByRole('heading', { level: 1 })).toHaveTextContent(
    'Find benefits from a purchase',
  );
  expect(within(main).getByRole('form', { name: 'Check a purchase' })).toBeVisible();
  for (const label of ['Manufacturer / Brand', 'Product model or SKU', 'Retailer', 'Purchase date'])
    expect(screen.getByLabelText(label)).toBeRequired();
  expect(screen.getByRole('button', { name: 'Find My Benefits' })).toHaveAttribute(
    'type',
    'submit',
  );
  expect(main).toHaveAttribute('id', 'main-content');
  expect(main).toHaveAttribute('tabindex', '-1');
});

it('lets visitors select an educational benefit guide', () => {
  render(
    <QueryProvider>
      <PurchaseCheckSessionProvider>
        <Home />
      </PurchaseCheckSessionProvider>
    </QueryProvider>,
  );

  const guide = screen.getByRole('region', { name: 'Types of benefits' });
  const cashback = within(guide).getByRole('button', { name: /cashback/i });
  const warranty = within(guide).getByRole('button', { name: /extended warranty/i });
  expect(cashback).toHaveAttribute('aria-expanded', 'true');
  expect(within(guide).getAllByText(/official terms are authoritative/i)[0]).toBeVisible();
  fireEvent.click(warranty);
  expect(warranty).toHaveAttribute('aria-expanded', 'true');
  expect(cashback).toHaveAttribute('aria-expanded', 'false');
  expect(within(guide).getByText(/cover beyond the original warranty/i)).toBeVisible();
  fireEvent.click(warranty);
  expect(warranty).toHaveAttribute('aria-expanded', 'false');
});
