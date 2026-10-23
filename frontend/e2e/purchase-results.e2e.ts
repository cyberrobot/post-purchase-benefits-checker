import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { expectReflow } from './support-layout';
async function check(page: Page, model = 'POPULATED', path = '/check') {
  await page.goto(path);
  await page.getByLabel('Manufacturer / Brand', { exact: true }).fill('Submitted brand');
  await page.getByLabel('Product model or SKU', { exact: true }).fill(model);
  await page.getByLabel('Retailer', { exact: true }).fill('Submitted shop');
  await page.getByLabel('Purchase date', { exact: true }).fill('2024-02-29');
  await page.getByRole('button', { name: 'Find My Benefits' }).click();
  await expect(page).toHaveURL('/results');
}
async function axe(page: Page) {
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
        .analyze()
    ).violations,
  ).toEqual([]);
}
for (const path of ['/', '/check']) {
  test(`explicit check from ${path} hands off exactly once with truthful purchase and safe details`, async ({
    page,
  }) => {
    const requests: string[] = [];
    page.on('request', (request) => {
      if (request.url().includes('/api/'))
        requests.push(`${request.method()} ${new URL(request.url()).pathname}`);
    });
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('console', (message) => {
      if (message.type() === 'error') errors.push(message.text());
    });
    await check(page, 'POPULATED', path);
    await expect(page.locator('body > main#main-content')).toHaveCount(1);
    await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
    await expect(page.getByRole('main')).toBeFocused();
    await expect(page.getByRole('heading', { name: 'Submitted brand · POPULATED' })).toBeVisible();
    await expect(page.getByRole('main')).toContainText('Submitted shop');
    await expect(page.getByRole('main')).toContainText('29 Feb 2024');
    await expect(page.getByRole('main')).toContainText('08 Oct 2026');
    await expect(page.getByRole('main')).not.toContainText(
      /Paid amount|ONLINE|Invoice date|Purchase verified/,
    );
    const card = page.getByRole('article');
    await expect(card.getByRole('heading', { name: '£10.00 cashback' })).toBeVisible();
    await expect(card).toContainText('Source last verified: 2 Oct 2026');
    await expect(card).toContainText('not an approved or paid claim');
    const summary = card.locator('summary', { hasText: 'View claim requirements' });
    await summary.focus();
    await page.keyboard.press('Enter');
    await expect(card.getByText('Keep your receipt.')).toBeVisible();
    const rules = card.locator('summary', { hasText: 'Recorded rules' });
    await rules.focus();
    await page.keyboard.press('Enter');
    await expect(card.getByText('product: satisfied')).toBeVisible();
    for (const [label, href] of [
      ['Official promotion source / terms', 'https://example.com/offer'],
      ['Open official claim site', 'https://example.com/claim'],
    ]) {
      const link = card.getByRole('link', { name: new RegExp(label) });
      await expect(link).toHaveAttribute('href', href);
      await expect(link).toHaveAttribute('target', '_blank');
      await expect(link).toHaveAttribute('rel', /noopener noreferrer/);
    }
    await axe(page);
    expect(requests).toEqual(['POST /api/eligibility/check']);
    expect(
      await page.evaluate(() => ({
        local: localStorage.length,
        session: sessionStorage.length,
        cookie: document.cookie,
        history: JSON.stringify(history.state),
      })),
    ).toEqual({
      local: 0,
      session: 0,
      cookie: '',
      history: expect.not.stringContaining('Submitted brand'),
    });
    expect(errors).toEqual([]);
  });
}
test('all six variants survive status filtering with stable totals and zero additional network', async ({
  page,
}) => {
  let requests = 0;
  page.on('request', (request) => {
    if (request.url().includes('/api/')) requests++;
  });
  await check(page, 'MIXED');
  await expect(page.getByRole('article')).toHaveCount(6);
  for (const [label, count] of [
    ['Eligible', 1],
    ['Potentially eligible', 1],
    ['Upcoming claim period', 1],
    ['Claim period expired', 1],
    ['Not eligible', 2],
  ] as const) {
    const filter = page.getByRole('button', { name: `${label} (${count})`, exact: true });
    await filter.focus();
    await page.keyboard.press('Enter');
    await expect(filter).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByRole('article')).toHaveCount(count);
    await expect(page.getByRole('status')).toContainText(`Showing ${count} of 6`);
  }
  await axe(page);
  await page.getByRole('button', { name: 'All (6)', exact: true }).click();
  await expect(page.getByRole('article')).toHaveCount(6);
  expect(requests).toBe(1);
});
test('empty category has an accessible reset and published no-match remains distinct', async ({
  page,
}) => {
  await check(page);
  await page.getByRole('button', { name: 'Not eligible (0)', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'No results in this category' })).toBeVisible();
  await axe(page);
  await page.getByRole('button', { name: 'Show all results' }).click();
  await expect(page.getByRole('article')).toHaveCount(1);
  await page.getByRole('link', { name: 'Edit purchase details' }).click();
  await page.getByLabel('Product model or SKU', { exact: true }).fill('NO_MATCH');
  await page.getByRole('button', { name: 'Find My Benefits' }).click();
  await expect(
    page.getByRole('heading', { name: 'No matching published promotions' }),
  ).toBeVisible();
  await axe(page);
});
test('editing immediately invalidates old results across history and a new check replaces the snapshot', async ({
  page,
}) => {
  let requests = 0;
  page.on('request', (request) => {
    if (request.url().includes('/api/')) requests++;
  });
  await check(page);
  await page.getByRole('link', { name: 'Edit purchase details' }).click();
  await expect(page.getByLabel('Product model or SKU', { exact: true })).toHaveValue('POPULATED');
  await page.getByLabel('Product model or SKU', { exact: true }).fill('MIXED');
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'No results in this tab' })).toBeVisible();
  await page.goForward();
  await expect(page.getByLabel('Product model or SKU', { exact: true })).toHaveValue('MIXED');
  expect(requests).toBe(1);
  await page.getByRole('button', { name: 'Find My Benefits' }).click();
  await expect(page.getByRole('heading', { name: 'Submitted brand · MIXED' })).toBeVisible();
  await expect(page.getByRole('article')).toHaveCount(6);
  expect(requests).toBe(2);
});
test('direct entry, reload and another tab have no snapshot and issue no implicit check', async ({
  page,
  context,
}) => {
  let requests = 0;
  context.on('request', (request) => {
    if (request.url().includes('/api/')) requests++;
  });
  await page.goto('/results');
  await expect(page.getByRole('heading', { name: 'No results in this tab' })).toBeVisible();
  await axe(page);
  await page.getByRole('link', { name: 'Start a purchase check' }).click();
  await expect(page.getByRole('form')).toBeVisible();
  expect(requests).toBe(0);
  await check(page);
  const another = await context.newPage();
  await another.goto('/results');
  await expect(another.getByRole('heading', { name: 'No results in this tab' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'No results in this tab' })).toBeVisible();
  expect(requests).toBe(1);
});
for (const model of ['UNKNOWN', 'AMBIGUOUS']) {
  test(`unresolved ${model} is accessible and correctable without internal identities`, async ({
    page,
  }) => {
    await check(page, model);
    await expect(
      page.getByRole('heading', { name: 'Check your product model or SKU' }),
    ).toBeVisible();
    await expect(page.getByRole('main')).not.toContainText(/00000000|not eligible/i);
    await axe(page);
    await page.getByRole('link', { name: 'Edit purchase details', exact: true }).first().click();
    await expect(page.getByLabel('Product model or SKU', { exact: true })).toHaveValue(model);
    await page.getByLabel('Product model or SKU', { exact: true }).fill('POPULATED');
    await page.getByRole('button', { name: 'Find My Benefits' }).click();
    await expect(page.getByRole('article')).toHaveCount(1);
  });
}
for (const width of [320, 360, 375, 768, 1024, 1280, 1440]) {
  test(`results cards and expanded details reflow at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await check(page, 'MIXED');
    await page.getByRole('article').first().locator('summary').first().click();
    await expectReflow(page, width);
  });
}
for (const width of [320, 640]) {
  test(`results support 200% text and reduced motion at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await check(page, 'MIXED');
    await page.evaluate(() => {
      document.documentElement.style.fontSize = '200%';
    });
    await expectReflow(page, width);
  });
}

test('an unchanged recheck failure invalidates results across history and preserves manual retry', async ({
  page,
}) => {
  let requests = 0;
  page.on('request', (request) => {
    if (request.url().includes('/api/eligibility/check')) requests++;
  });
  await check(page);
  await page.getByRole('link', { name: 'Edit purchase details' }).click();
  await page.route(
    '**/api/eligibility/check',
    (route) => route.fulfill({ status: 503, contentType: 'application/json', body: '{}' }),
    { times: 1 },
  );
  await page.getByRole('button', { name: 'Find My Benefits' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page).toHaveURL('/check');
  await expect(page.getByLabel('Product model or SKU', { exact: true })).toHaveValue('POPULATED');
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'No results in this tab' })).toBeVisible();
  await expect(page.getByRole('article')).toHaveCount(0);
  await page.goForward();
  for (const [label, value] of [
    ['Manufacturer / Brand', 'Submitted brand'],
    ['Product model or SKU', 'POPULATED'],
    ['Retailer', 'Submitted shop'],
    ['Purchase date', '2024-02-29'],
  ]) {
    await expect(page.getByLabel(label, { exact: true })).toHaveValue(value);
  }
  expect(requests).toBe(2);
  await page.route(
    '**/api/eligibility/check',
    async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.promotions[0].promotion_name = 'Fresh retry response';
      await route.fulfill({ response, json: body });
    },
    { times: 1 },
  );
  await page.getByRole('button', { name: 'Find My Benefits' }).click();
  await expect(page).toHaveURL('/results');
  await expect(page.getByRole('heading', { name: 'Fresh retry response' })).toBeVisible();
  await expect(page.getByRole('article')).toHaveCount(1);
  expect(requests).toBe(3);
});
