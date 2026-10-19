import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { renderToString } from 'react-dom/server';
import { SiteHeader } from './SiteHeader';
import { SiteNavigation } from './SiteNavigation';

it('publishes only the home destination when no additional navigation exists', () => {
  render(<SiteHeader />);
  expect(screen.getByRole('link', { name: 'BenefitScout' })).toHaveAttribute('href', '/');
  expect(screen.getAllByRole('link')).toHaveLength(1);
  expect(screen.queryByText('Menu')).not.toBeInTheDocument();
});

it('leaves the server-rendered native disclosure state to the browser', () => {
  const html = renderToString(
    <SiteNavigation items={[{ href: '#main-content', label: 'Page content' }]} />,
  );
  const summary = html.match(/<summary[^>]*>/)?.[0];
  expect(summary).toBeDefined();
  expect(summary).not.toContain('aria-expanded');
});

it('supports real supplied links and a native mobile disclosure with Escape focus restoration', async () => {
  render(<SiteHeader navigation={[{ href: '#main-content', label: 'Page content' }]} />);
  const summary = screen.getByText('Menu');
  const details = summary.closest('details');
  expect(summary).toHaveAttribute('aria-expanded', 'false');
  const desktop = screen.getByRole('navigation', { name: 'Primary' });
  expect(within(desktop).getByRole('link', { name: 'Page content' })).toHaveAttribute(
    'href',
    '#main-content',
  );
  expect(details).not.toHaveAttribute('open');
  fireEvent.click(summary);
  await waitFor(() => expect(summary).toHaveAttribute('aria-expanded', 'true'));
  const mobile = screen.getByRole('navigation', { name: 'Mobile primary' });
  expect(summary).toHaveAttribute('aria-controls', mobile.id);
  const link = within(mobile).getByRole('link', { name: 'Page content' });
  link.focus();
  fireEvent.keyDown(link, { key: 'Escape' });
  expect(details).not.toHaveAttribute('open');
  expect(summary).toHaveFocus();
  expect(summary).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(summary);
  await waitFor(() => expect(summary).toHaveAttribute('aria-expanded', 'true'));
  fireEvent.click(link);
  expect(details).not.toHaveAttribute('open');
  expect(summary).toHaveAttribute('aria-expanded', 'false');
});
