import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { expectReadable, expectReflow } from './support-layout';

const path = '/promotions/example--claim-checklist/claim';
const first = '00000000-0000-0000-0000-000000000005';
const empty = '00000000-0000-0000-0000-000000000025';
const selectedPath = path + '?variant=' + first;
const claimLink = { name: 'Open official claim site (opens in a new tab)' };

async function axe(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze();
  expect(result.violations).toEqual([]);
}

test('selects, marks and resets a published checklist without a purchase session or storage', async ({
  page,
  context,
}) => {
  const posts: string[] = [];
  const errors: string[] = [];
  context.on('request', (request) => {
    if (request.method() === 'POST') posts.push(request.url());
  });
  context.on('weberror', (error) => errors.push(error.error().message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });

  await page.goto(path);
  await expect(page.getByText('Choose a promotion variant to see its requirements.')).toBeVisible();
  await expect(page.getByRole('checkbox')).toHaveCount(0);
  await axe(page);
  await page.getByRole('link', { name: /Base offer.*Example Retailer.*TV-100/ }).click();
  await expect(page).toHaveURL(selectedPath);
  await expect(page.getByRole('link', { name: /Base offer.*selected/ })).toHaveAttribute(
    'aria-current',
    'page',
  );
  const [original, duplicate, registration] = await page.getByRole('checkbox').all();
  expect(await page.getByRole('checkbox').count()).toBe(3);
  await expect(original).toHaveAccessibleDescription('Keep your receipt.');
  await expect(duplicate).toHaveAccessibleDescription('Keep a duplicate receipt.');
  await expect(registration).toHaveAccessibleName('Registration');
  const before = await page.evaluate(() => [
    localStorage.length,
    sessionStorage.length,
    document.cookie,
  ]);

  const progress = page.getByRole('status');
  await expect(progress).toContainText('0 of 3 items marked ready.');
  await original.focus();
  await expect(original).toBeFocused();
  await page.keyboard.press('Space');
  await expect(original).toBeChecked();
  await expect(duplicate).not.toBeChecked();
  await expect(progress).toContainText('1 of 3 items marked ready.');
  await expect(page.getByRole('link', claimLink)).toBeVisible();
  await page.keyboard.press('Tab');
  await expect(duplicate).toBeFocused();
  await duplicate.check();
  await registration.check();
  await expect(progress).toContainText('All recorded items marked ready.');
  await duplicate.uncheck();
  await expect(progress).toContainText('2 of 3 items marked ready.');
  await expect(progress).not.toContainText('All recorded items marked ready.');
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length, document.cookie]),
  ).toEqual(before);

  for (const [name, href] of [
    [claimLink.name, 'https://example.com/claim'],
    ['Read official terms (opens in a new tab)', 'https://example.com/offer'],
  ]) {
    const link = page.getByRole('link', { name });
    await expect(link).toHaveAttribute('href', href);
    await expect(link).toHaveAttribute('target', '_blank');
    await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  }

  await page.getByRole('link', { name: /special.*TV-100/ }).click();
  await expect(page).toHaveURL(path + '?variant=' + empty);
  await expect(page.getByText(/No claim requirements are recorded for this variant/)).toBeVisible();
  await expect(page.getByRole('checkbox')).toHaveCount(0);
  await expect(page.getByRole('status')).toHaveCount(0);
  await expect(page.getByRole('link', claimLink)).toBeVisible();
  await axe(page);
  await page.goBack();
  await expect(page).toHaveURL(selectedPath);
  await expect(progress).toContainText('0 of 3 items marked ready.');
  await page.goForward();
  await expect(page.getByText(/No claim requirements are recorded for this variant/)).toBeVisible();

  const fresh = await context.newPage();
  await fresh.goto(selectedPath);
  await expect(fresh.getByRole('checkbox').first()).not.toBeChecked();
  await fresh.getByRole('checkbox').first().check();
  await fresh.reload();
  await expect(fresh.getByRole('status')).toContainText('0 of 3 items marked ready.');
  expect(posts).toEqual([]);
  expect(errors).toEqual([]);
});

test('auto-selects the only variant and connects back to the matching details section', async ({
  page,
}) => {
  await page.goto('/promotions/example--single-claim/claim');
  await expect(page.getByRole('checkbox', { name: 'Receipt' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Promotion variants' })).toHaveCount(0);
  await page.getByRole('link', { name: 'Back to promotion details' }).click();
  await expect(page.locator('#variant-' + first)).toBeFocused();
  await page.getByRole('link', { name: 'Prepare claim checklist' }).click();
  await expect(page).toHaveURL('/promotions/example--single-claim/claim?variant=' + first);
  await expect(page.getByRole('checkbox', { name: 'Receipt' })).toBeVisible();
});

for (const [name, url] of [
  ['missing', '/promotions/example--missing/claim'],
  ['hidden', '/promotions/example--hidden/claim'],
  ['malformed slug', '/promotions/Example--claim-checklist/claim'],
  ['encoded slug', '/promotions/ex%61mple--claim-checklist/claim'],
  ['invalid UUID', path + '?variant=invalid'],
  ['unknown UUID', path + '?variant=00000000-0000-0000-0000-000000000500'],
  ['repeated UUID', selectedPath + '&variant=' + first],
]) {
  test('returns the public 404 for ' + name, async ({ page }) => {
    expect((await page.goto(url))?.status()).toBe(404);
    await expect(page.getByRole('heading', { name: 'Promotion not found' })).toBeVisible();
    await expect(page.getByRole('link', claimLink)).toHaveCount(0);
  });
}

for (const slug of ['unavailable', 'malformed', 'unsafe']) {
  test('provides a safe retry state for ' + slug, async ({ page }) => {
    await page.goto('/promotions/example--' + slug + '/claim');
    await expect(
      page.getByRole('heading', { name: 'Promotion details unavailable' }),
    ).toBeVisible();
    await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible();
    await expect(page.getByRole('link', claimLink)).toHaveCount(0);
    if (slug === 'unavailable') await axe(page);
  });
}

test('supports keyboard skip navigation and wide and narrow reflow', async ({ page }) => {
  await page.goto(selectedPath);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('main')).toBeFocused();
  await axe(page);
  for (const width of [320, 360, 375, 768, 1024, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await expectReflow(page, width);
    await expectReadable(page.getByRole('link', claimLink), width);
    await expectReadable(page.getByText('Keep a duplicate receipt.'), width);
  }
  await page.setViewportSize({ width: 320, height: 900 });
  await page.evaluate(() => {
    document.documentElement.style.fontSize = '200%';
  });
  await expectReflow(page, 320);
  await expectReadable(page.getByRole('link', claimLink), 320);
  await expectReadable(page.getByText('Keep a duplicate receipt.'), 320);
});
