import { render, screen } from '@testing-library/react';
import RootLayout from './layout';
import Home from './page';

it('composes a skip link, banner, one page main and heading, and contentinfo', () => {
  const layout = RootLayout({ children: <Home /> });
  // Render the body children: jsdom already supplies the document html/body.
  render(layout.props.children.props.children);
  expect(screen.getByRole('banner')).toBeInTheDocument();
  expect(screen.getByRole('contentinfo')).toBeInTheDocument();
  expect(screen.getAllByRole('main')).toHaveLength(1);
  expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
  expect(screen.getByRole('link', { name: 'Skip to main content' })).toHaveAttribute(
    'href',
    `#${screen.getByRole('main').id}`,
  );
  expect(screen.getAllByRole('link').map((link) => link.getAttribute('href'))).toEqual([
    '#main-content',
    '/',
  ]);
});

it('keeps an ordinary future page main directly inside the shared shell', () => {
  const layout = RootLayout({
    children: (
      <main id="main-content" tabIndex={-1}>
        <h1>Ordinary page</h1>
      </main>
    ),
  });
  const body = layout.props.children;
  const children = body.props.children;
  expect(children.filter((child: React.ReactElement) => child?.type === 'main')).toHaveLength(1);
  render(children);
  const main = screen.getByRole('main');
  expect(main).toHaveAttribute('tabindex', '-1');
  expect(
    screen.getByRole('banner').compareDocumentPosition(main) & Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy();
  expect(
    main.compareDocumentPosition(screen.getByRole('contentinfo')) &
      Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy();
});
