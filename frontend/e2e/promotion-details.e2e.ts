import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { expectReadable, expectReflow } from './support-layout';

const route = '/promotions/example--populated-promotion';
const firstVariant = 'variant-00000000-0000-0000-0000-000000000005';

async function axe(page: Page) {
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
        .analyze()
    ).violations,
  ).toEqual([]);
}

test('links from results, supports browser back and loads without a purchase session', async ({
  page,
  context,
}) => {
  const posts: string[] = [];
  context.on('request', (request) => {
    if (request.method() === 'POST') posts.push(new URL(request.url()).pathname);
  });
  const errors: string[] = [];
  context.on('weberror', (error) => errors.push(error.error().message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  await page.goto('/check');
  await page.getByLabel('Manufacturer / Brand', { exact: true }).fill('Submitted maker');
  await page.getByLabel('Product model or SKU', { exact: true }).fill('POPULATED');
  await page.getByLabel('Retailer', { exact: true }).fill('Submitted shop');
  await page.getByLabel('Purchase date', { exact: true }).fill('2024-02-29');
  await page.getByRole('button', { name: 'Find My Benefits' }).click();
  await expect(page).toHaveURL('/results');
  await page.getByRole('link', { name: 'View promotion page' }).click();
  await expect(page).toHaveURL(route + '#' + firstVariant);
  await expect(page.locator('#' + firstVariant)).toBeVisible();
  await expect(page.locator('#' + firstVariant)).toBeFocused();
  expect(
    await page.locator('#' + firstVariant).evaluate((node) => node.getBoundingClientRect().top),
  ).toBeGreaterThanOrEqual(0);
  await expect(
    page.getByRole('heading', { name: 'Example populated promotion', level: 1 }),
  ).toBeVisible();
  await expect(page.getByRole('region')).toHaveCount(2);
  await expect(page.getByText(/At least 14 days after purchase/)).toBeVisible();
  await expect(page.getByText('2024-02-29')).toHaveCount(0);
  for (const [name, href] of [
    [/Read official terms/, 'https://example.com/offer'],
    [/Visit official claim site/, 'https://example.com/claim'],
    [/^Terms /, 'https://example.com/terms.pdf'],
  ] as const) {
    const link = page.getByRole('link', { name });
    await expect(link).toHaveAttribute('href', href);
    await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  }
  await page.goBack();
  await expect(page.getByRole('link', { name: 'View promotion page' })).toBeVisible();
  const fresh = await context.newPage();
  await fresh.goto(route);
  await expect(fresh.getByText('Other Television: £40.00 cashback')).toBeVisible();
  await fresh.reload();
  await expect(
    fresh.getByRole('heading', { name: 'Example populated promotion', level: 1 }),
  ).toBeVisible();
  await fresh.getByRole('link', { name: 'Check my purchase' }).click();
  await expect(fresh).toHaveURL('/check');
  expect(posts).toEqual(['/api/eligibility/check']);
  expect(errors).toEqual([]);
});

test('distinguishes matching stored slugs by manufacturer and displays relative rules', async ({
  page,
}) => {
  await page.goto('/promotions/another-maker--populated-promotion');
  await expect(
    page.getByRole('heading', { name: 'Another recorded promotion', level: 1 }),
  ).toBeVisible();
  await expect(page.getByText('Another Maker · Recorded as expired')).toBeVisible();
  await expect(page.getByText('Deadline 45 calendar days after purchase.')).toBeVisible();
  await expect(page.getByText(/No claim requirements recorded here/)).toBeVisible();
});

for (const slug of [
  'example--hidden',
  'example--missing',
  'EXAMPLE--invalid',
  'example--too--many',
]) {
  test('renders the public 404 for ' + slug, async ({ page }) => {
    const response = await page.goto('/promotions/' + slug);
    expect(response?.status()).toBe(404);
    await expect(page.getByRole('heading', { name: 'Promotion not found' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Check my purchase' })).toHaveAttribute(
      'href',
      '/check',
    );
  });
}

for (const slug of ['ex%61mple--populated-promotion', 'example--bad%ZZ']) {
  test('rejects encoded promotion slug ' + slug, async ({ page }) => {
    const response = await page.goto('/promotions/' + slug);
    expect(response?.status()).toBe(404);
    await expect(page.getByRole('heading', { name: 'Promotion not found' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Check my purchase' })).toHaveAttribute(
      'href',
      '/check',
    );
  });
}

for (const slug of ['unavailable', 'malformed', 'unsafe']) {
  test('shows a recoverable error for ' + slug, async ({ page }) => {
    const response = await page.goto('/promotions/example--' + slug);
    expect(response?.status()).not.toBe(404);
    await expect(
      page.getByRole('heading', { name: 'Promotion details unavailable' }),
    ).toBeVisible();
    await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible();
    await expect(page.getByRole('link', { name: /Visit official claim site/ })).toHaveCount(0);
    if (slug === 'unavailable') await axe(page);
  });
}

test('supports keyboard skip navigation and 200 percent reflow across viewport widths', async ({
  page,
}) => {
  await page.goto(route);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('main')).toBeFocused();
  await axe(page);
  for (const width of [320, 360, 375, 768, 1024, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await expectReflow(page, width);
    await expectReadable(page.getByRole('heading', { name: 'Official sources and terms' }), width);
  }
  await page.setViewportSize({ width: 320, height: 900 });
  await page.evaluate(() => {
    document.documentElement.style.fontSize = '200%';
  });
  await expectReflow(page, 320);
  await expectReadable(page.getByRole('heading', { name: 'Official sources and terms' }), 320);
});
