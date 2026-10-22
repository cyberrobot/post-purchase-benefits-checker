import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { expectReadable, expectReflow } from './support-layout';

const heading = 'Find benefits from a purchase';

test('public shell has truthful content, landmarks and working home navigation', async ({
  page,
}) => {
  const response = await page.goto('/');
  expect(response?.status()).toBe(200);
  await expect(page.locator('html')).toHaveAttribute('lang', 'en-GB');
  await expect(page).toHaveTitle('BenefitScout');
  await expect(page.locator('main')).toHaveCount(1);
  await expect(page.locator('main#main-content')).toHaveCount(1);
  await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(heading);
  await expect(page.getByRole('banner')).toHaveCount(1);
  await expect(page.getByRole('contentinfo')).toHaveCount(1);
  await expect(page.getByRole('main')).toContainText(heading);
  await expect(page.getByRole('form', { name: 'Check a purchase' })).toBeVisible();
  await expect(page.locator('main input[required]')).toHaveCount(4);
  await expect(page.getByRole('button', { name: 'Find My Benefits' })).toBeVisible();
  await expect(page.getByRole('navigation')).toHaveCount(0);
  await expect(page.locator('header details, header button, footer a')).toHaveCount(0);
  const brand = page.getByRole('banner').getByRole('link', { name: 'BenefitScout', exact: true });
  await expect(page.getByRole('banner').getByRole('link')).toHaveCount(1);
  await page.evaluate(() => history.replaceState(null, '', '/?home-link-test=1'));
  await brand.click();
  await expect(page).toHaveURL('http://127.0.0.1:3101/');
  await expect(page.getByRole('main')).toContainText(heading);
});

for (const width of [320, 360, 375, 768, 1024, 1280, 1440]) {
  test(`shell reflows without clipped text or overlap at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/');
    await expectReflow(page, width);
    await page.getByRole('button', { name: 'Find My Benefits' }).click();
    await expectReflow(page, width);
  });
}

for (const width of [640, 320]) {
  test(`CSS-width reflow proxy at ${width}px with 200% text size`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await page.goto('/');
    await page.evaluate(() => {
      document.documentElement.style.fontSize = '200%';
    });
    await expectReflow(page, width);
    await page.getByRole('button', { name: 'Find My Benefits' }).click();
    await expectReflow(page, width);
  });
}

test('footer follows content and the short viewport scrolls naturally', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/');
  const footer = page.getByRole('contentinfo');
  const main = page.getByRole('main');
  const footerBox = await footer.boundingBox();
  const mainBox = await main.boundingBox();
  expect(footerBox!.y).toBeGreaterThanOrEqual(mainBox!.y + mainBox!.height - 1);
  expect(footerBox!.y + footerBox!.height).toBeGreaterThanOrEqual(799);
  expect(await footer.evaluate((element) => getComputedStyle(element).position)).not.toMatch(
    /fixed|absolute/,
  );
  await page.setViewportSize({ width: 320, height: 240 });
  expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeGreaterThan(240);
  await footer.scrollIntoViewIfNeeded();
  await expect(footer).toBeInViewport();
  expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
});

for (const width of [320, 640, 1280]) {
  test(`keyboard skip link and home link have visible focus at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await page.goto('/');
    const skip = page.getByRole('link', { name: 'Skip to main content' });
    const brand = page.getByRole('banner').getByRole('link', { name: 'BenefitScout', exact: true });
    await page.keyboard.press('Tab');
    await expect(skip).toBeFocused();
    await expectReadable(skip, width);
    const focus = await skip.evaluate((element) => {
      const style = getComputedStyle(element);
      return { style: style.outlineStyle, width: parseFloat(style.outlineWidth) };
    });
    expect(focus.style).not.toBe('none');
    expect(focus.width).toBeGreaterThanOrEqual(2);
    await page.keyboard.press('Tab');
    await expect(brand).toBeFocused();
    await expectReadable(brand, width);
    const brandFocus = await brand.evaluate((element) => {
      const style = getComputedStyle(element);
      return { style: style.outlineStyle, width: parseFloat(style.outlineWidth) };
    });
    expect(brandFocus.style).not.toBe('none');
    expect(brandFocus.width).toBeGreaterThanOrEqual(2);
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL('http://127.0.0.1:3101/');
    await page.goto('/');
    await page.keyboard.press('Tab');
    await expect(skip).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('main')).toBeFocused();
    const mainBox = await page.getByRole('main').boundingBox();
    expect(mainBox!.y).toBeGreaterThanOrEqual(-1);
    expect(
      await page.getByRole('banner').evaluate((element) => getComputedStyle(element).position),
    ).not.toMatch(/fixed|sticky/);
    // Reverse navigation keeps the actual header link reachable after the skip target.
    await page.keyboard.press('Shift+Tab');
    await expect(brand).toBeFocused();
  });
}

test('rendered root passes axe WCAG A/AA checks', async ({ page }) => {
  await page.goto('/');
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze();
  expect(results.violations).toEqual([]);
});

test('reduced motion leaves no animations on the current static shell', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  expect(await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches)).toBe(
    true,
  );
  expect(await page.evaluate(() => document.getAnimations().length)).toBe(0);
  const transitions = await page
    .locator('body *')
    .evaluateAll((elements) =>
      elements.map((element) => getComputedStyle(element).transitionDuration),
    );
  expect(
    transitions.every((duration) => duration.split(',').every((part) => parseFloat(part) === 0)),
  ).toBe(true);
});

test('root loads local assets without runtime errors or remote dependencies', async ({ page }) => {
  const errors: string[] = [];
  const failures: string[] = [];
  const remote: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('requestfailed', (request) =>
    failures.push(`${request.url()}: ${request.failure()?.errorText}`),
  );
  page.on('response', (response) => {
    if (response.status() >= 400) failures.push(`${response.status()} ${response.url()}`);
  });
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (url.protocol.startsWith('http') && url.origin !== 'http://127.0.0.1:3101')
      remote.push(url.href);
  });
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  expect(errors).toEqual([]);
  expect(failures).toEqual([]);
  expect(remote).toEqual([]);
});
