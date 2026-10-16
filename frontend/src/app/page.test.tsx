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
