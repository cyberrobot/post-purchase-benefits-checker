import { render, screen, within } from '@testing-library/react';
import Home from '@/app/page';

it('introduces BenefitScout and explains that purchase checking is not available yet', () => {
  render(<Home />);

  const main = screen.getByRole('main');
  expect(main).toBeInTheDocument();
  expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
  expect(within(main).getByRole('heading', { level: 1, name: 'BenefitScout' })).toBeVisible();
  expect(
    within(main).getByText(
      'We are establishing the BenefitScout web application. Purchase checking is not available yet.',
    ),
  ).toBeVisible();
});

it('provides a focusable main target for the shell skip link', () => {
  render(<Home />);
  expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content');
  expect(screen.getByRole('main')).toHaveAttribute('tabindex', '-1');
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});
