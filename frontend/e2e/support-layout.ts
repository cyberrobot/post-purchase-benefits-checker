import { expect, type Locator, type Page } from '@playwright/test';

export async function expectReadable(locator: Locator, viewportWidth: number) {
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

export async function expectReflow(page: Page, width: number) {
  const dimensions = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client + 1);
  const criticalText = [
    page.getByRole('banner').getByRole('link', { name: 'BenefitScout', exact: true }),
    page.getByRole('heading', { level: 1 }),
    ...(await page
      .locator(
        'form label:visible, form p:visible, form button, form summary, form [role="status"]:not(:empty)',
      )
      .all()),
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
  for (const control of await page.locator('form input:visible, form button').all()) {
    const box = await control.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.width).toBeGreaterThan(0);
    expect(box!.x).toBeGreaterThanOrEqual(-1);
    expect(box!.x + box!.width).toBeLessThanOrEqual(width + 1);
  }
  const boxes = await Promise.all(
    ['banner', 'main', 'contentinfo'].map((role) =>
      page.getByRole(role as 'banner' | 'main' | 'contentinfo').boundingBox(),
    ),
  );
  expect(boxes[0]!.y + boxes[0]!.height).toBeLessThanOrEqual(boxes[1]!.y + 1);
  expect(boxes[1]!.y + boxes[1]!.height).toBeLessThanOrEqual(boxes[2]!.y + 1);
}
