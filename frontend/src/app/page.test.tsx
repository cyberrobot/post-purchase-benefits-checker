import { render, screen, within } from '@testing-library/react';
import Home from '@/app/page';
import { QueryProvider } from '@/components/providers/QueryProvider';

it('introduces purchase checking with the actual four-field entry form', () => {
  render(
    <QueryProvider>
      <Home />
    </QueryProvider>,
  );
  const main = screen.getByRole('main');
  expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
  expect(within(main).getByRole('heading', { level: 1 })).toHaveTextContent(
    'Find benefits from a purchase',
  );
  expect(within(main).getByRole('form', { name: 'Check a purchase' })).toBeVisible();
  for (const label of ['Manufacturer', 'Model number', 'Retailer', 'Purchase date'])
    expect(screen.getByLabelText(label)).toBeRequired();
  expect(screen.getByRole('button', { name: 'Find My Benefits' })).toHaveAttribute(
    'type',
    'submit',
  );
  expect(main).toHaveAttribute('id', 'main-content');
  expect(main).toHaveAttribute('tabindex', '-1');
});
