import { render, screen } from '@testing-library/react';
import { QueryProvider, createQueryClient } from './QueryProvider';
it('adds no DOM wrapper and creates isolated clients', () => {
  const { container } = render(
    <QueryProvider>
      <main>Content</main>
    </QueryProvider>,
  );
  expect(container.firstElementChild).toBe(screen.getByRole('main'));
  expect(createQueryClient()).not.toBe(createQueryClient());
});
