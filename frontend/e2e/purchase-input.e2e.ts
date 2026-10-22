import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
async function fill(page: Page, model = 'SKU /-1') {
  await page.getByLabel('Manufacturer / Brand', { exact: true }).fill('Example');
  await page.getByLabel('Product model or SKU', { exact: true }).fill(model);
  await page.getByLabel('Retailer', { exact: true }).fill('Shop');
  await page.getByLabel('Purchase date', { exact: true }).fill('2024-02-29');
}
test('valid explicit UI submissions traverse the bridge once and clear stale completion', async ({
  page,
}) => {
  const requests: string[] = [];
  const errors: string[] = [];
  page.on('request', (request) => {
    if (request.url().endsWith('/api/eligibility/check')) requests.push(request.postData()!);
  });
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  await page.goto('/');
  expect(requests).toEqual([]);
  await page.getByRole('button', { name: 'Find My Benefits' }).click();
  await expect(page.getByLabel('Manufacturer / Brand', { exact: true })).toBeFocused();
  expect(requests).toEqual([]);
  await fill(page);
  expect(requests).toEqual([]);
  await page.getByRole('button', { name: 'Find My Benefits' }).click();
  await expect(page.getByRole('status')).toContainText('No matching published promotion');
  expect(requests).toHaveLength(1);
  expect(JSON.parse(requests[0])).toEqual({
    brand: 'Example',
    model: 'SKU /-1',
    retailer: 'Shop',
    purchase_date: '2024-02-29',
  });
  await page.getByLabel('Product model or SKU', { exact: true }).fill('UNKNOWN');
  await expect(page.getByRole('status')).toBeEmpty();
  expect(requests).toHaveLength(1);
  await page.getByRole('button', { name: 'Find My Benefits' }).click();
  await expect(page.getByRole('status')).toContainText('product model or sku could not be found');
  expect(requests).toHaveLength(2);
  await page.getByLabel('Product model or SKU', { exact: true }).fill('NOT_ELIGIBLE');
  await page.getByRole('button', { name: 'Find My Benefits' }).click();
  await expect(page.getByRole('status')).toContainText(
    '1 promotion match: does not meet recorded rules.',
  );
  expect(requests).toHaveLength(3);
  await expect(page.getByRole('status')).not.toContainText(/cashback|claimable|qualify|£/i);
  expect(errors).toEqual([]);
});
for (const [model, text] of [
  ['RATE', 'wait 15 seconds'],
  ['OFFLINE', 'temporarily unavailable'],
  ['UNSAFE', 'temporarily unavailable'],
]) {
  test(`rendered form safely handles ${model} and manual correction`, async ({ page }) => {
    let requests = 0;
    const errors: string[] = [];
    page.on('request', (request) => {
      if (request.url().endsWith('/api/eligibility/check')) requests++;
    });
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('console', (message) => {
      if (
        message.type() === 'error' &&
        !/^Failed to load resource: the server responded with a status of (429|502)/.test(
          message.text(),
        )
      )
        errors.push(message.text());
    });
    await page.goto('/');
    await fill(page, model);
    await page.getByRole('button', { name: 'Find My Benefits' }).click();
    const alert = page.getByRole('form', { name: 'Check a purchase' }).getByRole('alert');
    await expect(alert).toContainText(text);
    expect(requests).toBe(1);
    await expect(page.getByLabel('Product model or SKU', { exact: true })).toHaveValue(model);
    await expect(page.getByRole('status')).toBeEmpty();
    await page.getByLabel('Product model or SKU', { exact: true }).fill('SKU-1');
    await expect(alert).toHaveCount(0);
    expect(requests).toBe(1);
    await page.getByRole('button', { name: 'Find My Benefits' }).click();
    await expect(page.getByRole('status')).toContainText('No matching published promotion');
    expect(requests).toBe(2);
    expect(errors).toEqual([]);
  });
}
test('invalid form remains accessible and keyboard order follows the four fields', async ({
  page,
}) => {
  await page.goto('/');
  const manufacturer = page.getByLabel('Manufacturer / Brand', { exact: true });
  await manufacturer.focus();
  for (const label of ['Product model or SKU', 'Retailer', 'Purchase date']) {
    // Native date fields have several browser-managed segments; enter via Tab from retailer only.
    await page.keyboard.press('Tab');
    await expect(page.getByLabel(label, { exact: true })).toBeFocused();
    const outline = await page
      .getByLabel(label, { exact: true })
      .evaluate((element) => parseFloat(getComputedStyle(element).outlineWidth));
    expect(outline).toBeGreaterThanOrEqual(2);
  }
  await page.getByRole('button', { name: 'Find My Benefits' }).click();
  await expect(manufacturer).toBeFocused();
  await expect(manufacturer).toHaveAttribute('aria-invalid', 'true');
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze();
  expect(results.violations).toEqual([]);
});
