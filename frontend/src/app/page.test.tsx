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

it('explains the journey after the embedded checker without linking away', () => {
  render(
    <QueryProvider>
      <PurchaseCheckSessionProvider>
        <Home />
      </PurchaseCheckSessionProvider>
    </QueryProvider>,
  );
  const main = screen.getByRole('main');
  expect(
    within(main).queryByRole('link', { name: /dedicated purchase checker/i }),
  ).not.toBeInTheDocument();
  const steps = screen.getByText('Enter purchase details').closest('ol')!;
  expect(
    within(steps)
      .getAllByRole('listitem')
      .map((item) => item.textContent),
  ).toEqual([
    expect.stringContaining('Enter purchase details'),
    expect.stringContaining('Review matching published promotions'),
    expect.stringContaining('Follow official claim instructions'),
  ]);
  expect(
    screen.getByRole('form', { name: 'Check a purchase' }).compareDocumentPosition(steps) &
      Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy();
});

it('lets visitors select an educational benefit guide', () => {
  window.innerWidth = 320;
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
  window.innerWidth = 1024;
});

it('keeps a guide selected on desktop, including after resizing from a closed mobile guide', () => {
  window.innerWidth = 1024;
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
  fireEvent.click(cashback);
  expect(cashback).toHaveAttribute('aria-expanded', 'true');
  expect(within(guide).getByText(/money returned after purchase/i)).toBeVisible();

  window.innerWidth = 320;
  fireEvent(window, new Event('resize'));
  fireEvent.click(warranty);
  fireEvent.click(warranty);
  expect(warranty).toHaveAttribute('aria-expanded', 'false');
  expect(within(guide).getByText(/cover beyond the original warranty/i)).not.toBeVisible();

  window.innerWidth = 1024;
  fireEvent(window, new Event('resize'));
  expect(warranty).toHaveAttribute('aria-expanded', 'true');
  expect(within(guide).getByText(/cover beyond the original warranty/i)).toBeVisible();
  fireEvent.click(warranty);
  expect(warranty).toHaveAttribute('aria-expanded', 'true');
});
