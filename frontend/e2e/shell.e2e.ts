import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';

const placeholder = 'Purchase checking is not available yet.';

async function expectReadable(locator: Locator, viewportWidth: number) {
  await expect(locator).toBeVisible();
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.width).toBeGreaterThan(0);
  expect(box!.x).toBeGreaterThanOrEqual(-1);
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewportWidth + 1);
  // Text fragments must fit their own element and the viewport, not merely the document.
  const textLayout = await locator.evaluate((element) => {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    const fragments: { left: number; right: number; top: number; bottom: number }[] = [];
    const seenFragments = new Set<string>();
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (!node.textContent?.trim()) continue;
      // Decorative inline descendants (such as the brand's aria-hidden punctuation) can
      // contribute a duplicate Range rectangle. They are not readable text to validate.
      if (node.parentElement?.closest('[aria-hidden="true"]')) continue;
      const range = document.createRange();
      range.selectNode(node);
      for (const { left, right, top, bottom } of range.getClientRects()) {
        const key = `${left}:${right}:${top}:${bottom}`;
        if (seenFragments.has(key)) continue;
        seenFragments.add(key);
        fragments.push({ left, right, top, bottom });
      }
    }
    const clippingAncestors = [];
    for (let ancestor = element.parentElement; ancestor; ancestor = ancestor.parentElement) {
      const style = getComputedStyle(ancestor);
      const clipsX = style.overflowX !== 'visible';
      const clipsY = style.overflowY !== 'visible';
      if (!clipsX && !clipsY) continue;
      const rect = ancestor.getBoundingClientRect();
      clippingAncestors.push({
        left: rect.left + ancestor.clientLeft,
        right: rect.left + ancestor.clientLeft + ancestor.clientWidth,
        top: rect.top + ancestor.clientTop,
        bottom: rect.top + ancestor.clientTop + ancestor.clientHeight,
        clipsX,
        clipsY,
      });
    }
    return { fragments, clippingAncestors };
  });
  for (const fragment of textLayout.fragments) {
    expect(fragment.left).toBeGreaterThanOrEqual(-1);
    expect(fragment.right).toBeLessThanOrEqual(viewportWidth + 1);
    // Browser text metrics can extend by a pixel beyond a fractional element box after
    // layout rounding, so allow a two-pixel edge tolerance while still catching clipping.
    expect(fragment.top).toBeGreaterThanOrEqual(box!.y - 2);
    expect(fragment.bottom).toBeLessThanOrEqual(box!.y + box!.height + 2);
    for (const ancestor of textLayout.clippingAncestors) {
      if (ancestor.clipsX) {
        expect(fragment.left).toBeGreaterThanOrEqual(ancestor.left - 1);
        expect(fragment.right).toBeLessThanOrEqual(ancestor.right + 1);
      }
      if (ancestor.clipsY) {
        expect(fragment.top).toBeGreaterThanOrEqual(ancestor.top - 1);
        expect(fragment.bottom).toBeLessThanOrEqual(ancestor.bottom + 1);
      }
    }
  }
  return textLayout.fragments;
}

async function expectReflow(page: Page, width: number) {
  const dimensions = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client + 1);
  const criticalText = [
    page.getByRole('banner').getByRole('link', { name: 'BenefitScout', exact: true }),
    page.getByRole('heading', { level: 1 }),
    page.getByRole('main').getByText(/Purchase checking is not available yet/),
    ...(await page.getByRole('contentinfo').getByRole('paragraph').all()),
  ];
  const textFragments = [];
  for (const [owner, locator] of criticalText.entries()) {
    textFragments.push(
      ...(await expectReadable(locator, width)).map((fragment) => ({ owner, fragment })),
    );
  }
  for (let first = 0; first < textFragments.length; first++) {
    for (let second = first + 1; second < textFragments.length; second++) {
      const { owner: firstOwner, fragment: a } = textFragments[first];
      const { owner: secondOwner, fragment: b } = textFragments[second];
      if (firstOwner === secondOwner) continue;
      const overlaps =
        Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 &&
        Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1;
      expect(
        overlaps,
        `critical text fragments ${first} and ${second} overlap at ${width}px: ${JSON.stringify({ a, b })}`,
      ).toBe(false);
    }
  }
  const boxes = await Promise.all(
    ['banner', 'main', 'contentinfo'].map((role) =>
      page.getByRole(role as 'banner' | 'main' | 'contentinfo').boundingBox(),
    ),
  );
  expect(boxes[0]!.y + boxes[0]!.height).toBeLessThanOrEqual(boxes[1]!.y + 1);
  expect(boxes[1]!.y + boxes[1]!.height).toBeLessThanOrEqual(boxes[2]!.y + 1);
}

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
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('BenefitScout');
  await expect(page.getByRole('banner')).toHaveCount(1);
  await expect(page.getByRole('contentinfo')).toHaveCount(1);
  await expect(page.getByRole('main')).toContainText(placeholder);
  await expect(page.getByRole('main')).toContainText('Application in development');
  await expect(page.getByRole('main').locator('input, button, form, [role="status"]')).toHaveCount(
    0,
  );
  await expect(page.getByRole('navigation')).toHaveCount(0);
  await expect(page.locator('header details, header button, footer a')).toHaveCount(0);
  const brand = page.getByRole('banner').getByRole('link', { name: 'BenefitScout', exact: true });
  await expect(page.getByRole('banner').getByRole('link')).toHaveCount(1);
  await page.evaluate(() => history.replaceState(null, '', '/?home-link-test=1'));
  await brand.click();
  await expect(page).toHaveURL('http://127.0.0.1:3101/');
  await expect(page.getByRole('main')).toContainText(placeholder);
});

for (const width of [320, 360, 375, 768, 1024, 1280, 1440]) {
  test(`shell reflows without clipped text or overlap at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/');
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
