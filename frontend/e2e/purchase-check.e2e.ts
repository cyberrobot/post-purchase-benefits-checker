import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { expectReflow } from './support-layout';
const labels = ['Manufacturer / Brand', 'Product model or SKU', 'Retailer', 'Purchase date'];
const submit = (page: Page) => page.getByRole('button', { name: 'Find My Benefits' });
async function fill(page: Page, model = 'Sku./-1 AB') {
  for (const [index, value] of ['Any Brand', model, 'Any Shop', '2024-02-29'].entries())
    await page.getByLabel(labels[index], { exact: true }).fill(value);
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
function requests(page: Page) {
  const sent: unknown[] = [];
  page.on('request', (request) => {
    if (request.url().endsWith('/api/eligibility/check')) {
      expect(request.method()).toBe('POST');
      sent.push(request.postDataJSON());
    }
  });
  return sent;
}
test('canonical page has server landmarks, honest empty controls, keyboard disclosure and one explicit exact request', async ({
  page,
}) => {
  const sent = requests(page);
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  await page.goto('/check');
  await expect(page.locator('body > main#main-content')).toHaveCount(1);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Check your purchase');
  await expect(page.locator('select')).toHaveCount(0);
  await expect(page.getByRole('status')).toBeEmpty();
  expect(sent).toEqual([]);
  await axe(page);
  await page.getByLabel(labels[0], { exact: true }).focus();
  for (const label of labels.slice(1)) {
    await page.keyboard.press('Tab');
    await expect(page.getByLabel(label, { exact: true })).toBeFocused();
  }
  // Date segments are browser-owned; focus the following semantic control directly.
  const disclosure = page.locator('summary', { hasText: 'Add optional purchase price' });
  await disclosure.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('details')).toHaveAttribute('open', '');
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('Purchase price (GBP)')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(submit(page)).toBeFocused();
  await fill(page);
  await page.getByLabel('Retailer', { exact: true }).blur();
  expect(sent).toEqual([]);
  await submit(page).click();
  await expect(page.getByRole('status')).toContainText('No matching published promotion');
  expect(sent).toEqual([
    { brand: 'Any Brand', model: 'Sku./-1 AB', retailer: 'Any Shop', purchase_date: '2024-02-29' },
  ]);
  await page.getByLabel('Purchase price (GBP)').fill('799.99');
  await expect(page.getByRole('status')).toBeEmpty();
  await submit(page).click();
  await expect(page.getByRole('status')).toContainText('No matching published promotion');
  expect(sent[1]).toEqual({
    brand: 'Any Brand',
    model: 'Sku./-1 AB',
    retailer: 'Any Shop',
    purchase_date: '2024-02-29',
    purchase_price: '799.99',
  });
  await page.getByLabel('Purchase price (GBP)').fill('');
  await submit(page).click();
  await expect(page.getByRole('status')).toContainText('No matching published promotion');
  expect(sent[2]).toEqual(sent[0]);
  expect(errors).toEqual([]);
});
test('missing SKU has a contrasting described error, committed focus and no POST; correction clears it', async ({
  page,
}) => {
  const sent = requests(page);
  await page.goto('/check');
  await fill(page);
  const model = page.getByLabel(labels[1], { exact: true });
  const normalBorder = await model.evaluate((element) => getComputedStyle(element).borderColor);
  await model.fill('');
  await submit(page).click();
  await expect(model).toBeFocused();
  await expect(model).toHaveAttribute('aria-invalid', 'true');
  await expect(model).toHaveAccessibleDescription(/Enter the product model or sku/);
  expect(await model.evaluate((element) => getComputedStyle(element).borderColor)).not.toBe(
    normalBorder,
  );
  await expect(
    page.getByRole('form', { name: 'Check a purchase' }).getByRole('alert'),
  ).toContainText('highlighted fields');
  expect(sent).toEqual([]);
  await axe(page);
  await model.fill('corrected');
  await expect(model).not.toHaveAttribute('aria-invalid');
  await expect(page.getByRole('form', { name: 'Check a purchase' }).getByRole('alert')).toHaveCount(
    0,
  );
  expect(sent).toEqual([]);
});
test('CTA defaults to navy, hovers violet and shows visible keyboard focus', async ({ page }) => {
  await page.goto('/check');
  const button = submit(page);
  await expect(button).toHaveCSS('background-color', 'rgb(16, 24, 47)');
  await button.hover();
  await expect(button).toHaveCSS('background-color', 'rgb(80, 70, 230)');
  await page.mouse.move(0, 0);
  await page.locator('summary').focus();
  await page.keyboard.press('Tab');
  await expect(button).toBeFocused();
  expect(
    await button.evaluate((element) => parseFloat(getComputedStyle(element).outlineWidth)),
  ).toBeGreaterThanOrEqual(2);
});
for (const [model, message] of [
  ['UNKNOWN', 'could not be found'],
  ['AMBIGUOUS', 'more specific'],
]) {
  test(`unresolved ${model} prompts correction and never exposes candidate IDs`, async ({
    page,
  }) => {
    const sent = requests(page);
    await page.goto('/check');
    await fill(page, model);
    await submit(page).click();
    await expect(page.getByRole('status')).toContainText(message);
    await expect(page.getByRole('status')).not.toContainText(/00000000|not eligible/i);
    await page.getByLabel(labels[1], { exact: true }).fill('corrected');
    await expect(page.getByRole('status')).toBeEmpty();
    expect(sent).toHaveLength(1);
    await submit(page).click();
    await expect(page.getByRole('status')).toContainText('No matching published promotion');
    expect(sent).toHaveLength(2);
  });
}
test('mixed classifications count every real record truthfully', async ({ page }) => {
  await page.goto('/check');
  await fill(page, 'MIXED');
  await submit(page).click();
  const status = page.getByRole('status');
  for (const message of [
    '1 promotion: meets recorded eligibility rules; this is not an approved or paid claim.',
    '1 promotion: may qualify; more evidence or information could be required.',
    '2 promotions: does not meet recorded rules.',
    '1 promotion: claim period has not opened.',
    '1 promotion: claim period has expired.',
  ])
    await expect(status).toContainText(message);
  await expect(status).not.toContainText(/£|cashback|claim approved/i);
  await axe(page);
});
for (const [model, message] of [
  ['RATE', 'wait 15 seconds'],
  ['OFFLINE', 'temporarily unavailable'],
  ['UNAVAILABLE', 'temporarily unavailable'],
  ['BAD_GATEWAY', 'temporarily unavailable'],
  ['TIMEOUT', 'incomplete'],
  ['MALFORMED', 'temporarily unavailable'],
  ['UNSAFE', 'temporarily unavailable'],
]) {
  test(`recoverable ${model} retains values and permits one manual retry`, async ({ page }) => {
    const sent = requests(page);
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('console', (message) => {
      if (
        message.type() === 'error' &&
        !/^Failed to load resource: the server responded with a status of (429|502|503|504)/.test(
          message.text(),
        )
      )
        errors.push(message.text());
    });
    await page.goto('/check');
    await fill(page, model);
    await submit(page).click();
    const alert = page.getByRole('form', { name: 'Check a purchase' }).getByRole('alert');
    await expect(alert).toContainText(message, { timeout: 12000 });
    await expect(alert).toContainText(/Support reference: [0-9a-f-]{36}/);
    await expect(page.getByRole('status')).toBeEmpty();
    await expect(page.getByLabel(labels[1], { exact: true })).toHaveValue(model);
    await expect(submit(page)).toBeEnabled();
    expect(sent).toHaveLength(1);
    await page.context().setOffline(true);
    await page.context().setOffline(false);
    await page.evaluate(() => window.dispatchEvent(new Event('online')));
    await expect(alert).toContainText(message);
    expect(sent).toHaveLength(1);
    await page.getByLabel(labels[1], { exact: true }).fill('corrected');
    await expect(alert).toHaveCount(0);
    await submit(page).click();
    await expect(page.getByRole('status')).toContainText('No matching published promotion');
    expect(sent).toHaveLength(2);
    expect(errors).toEqual([]);
  });
}
test('pending controls and announcements prevent duplicate clicks and Enter, and navigation never replays the result', async ({
  page,
}) => {
  const sent = requests(page);
  await page.goto('/check');
  await fill(page, 'SLOW');
  await submit(page).dblclick();
  await expect(page.getByRole('status')).toHaveText('Checking your purchase…');
  await expect(page.getByRole('button', { name: 'Checking…' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Checking…' })).not.toHaveCSS(
    'background-color',
    'rgb(80, 70, 230)',
  );
  for (const label of labels) await expect(page.getByLabel(label, { exact: true })).toBeDisabled();
  await page.keyboard.press('Enter');
  expect(sent).toHaveLength(1);
  await axe(page);
  await expect(page.getByRole('status')).toContainText('No matching published promotion');
  expect(sent).toHaveLength(1);
  await page.getByLabel(labels[1], { exact: true }).fill('SLOW');
  await submit(page).click();
  await expect(page.getByRole('status')).toContainText('Checking');
  await page.getByRole('banner').getByRole('link', { name: 'BenefitScout', exact: true }).click();
  await expect(page.getByRole('status')).toBeEmpty();
  await page.getByRole('link', { name: 'Open the dedicated purchase checker' }).click();
  await expect(page.getByLabel(labels[0], { exact: true })).toHaveValue('');
  await expect(page.getByRole('status')).toBeEmpty();
  expect(sent).toHaveLength(2);
});
for (const width of [320, 360, 375, 768, 1024, 1280, 1440]) {
  test(`check page reflows with optional price, invalid and classified states at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/check');
    await page.locator('summary').click();
    await expectReflow(page, width);
    await submit(page).click();
    await expectReflow(page, width);
    await fill(page, 'MIXED');
    await submit(page).click();
    await expect(page.getByRole('status')).toContainText('claim period has expired');
    await expectReflow(page, width);
  });
}
for (const width of [320, 640]) {
  test(`check page reflows with 200% root text at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/check');
    await page.evaluate(() => {
      document.documentElement.style.fontSize = '200%';
    });
    await page.locator('summary').click();
    await submit(page).click();
    await expectReflow(page, width);
    await fill(page, 'MIXED');
    await submit(page).click();
    await expect(page.getByRole('status')).toContainText('claim period has expired');
    await expectReflow(page, width);
  });
}
test('check skip link focuses the page main', async ({ page }) => {
  await page.goto('/check');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('main')).toBeFocused();
});
