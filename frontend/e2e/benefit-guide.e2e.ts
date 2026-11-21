import { expect, test } from '@playwright/test';
import { expectReadable, expectReflow } from './support-layout';

for (const width of [320, 1280]) {
  test(`benefit guide supports keyboard exploration at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await page.goto('/');
    const guide = page.getByRole('region', { name: 'Types of benefits' });
    const cashback = guide.getByRole('button', { name: /cashback/i });
    const warranty = guide.getByRole('button', { name: /extended warranty/i });
    const gift = guide.getByRole('button', { name: /free gift/i });
    await expect(cashback).toHaveAttribute('aria-expanded', 'true');
    await expect(warranty).toHaveAttribute('aria-expanded', 'false');
    const initialPanel = page.locator(`[id="${await cashback.getAttribute('aria-controls')}"]`);
    await expect(initialPanel).toBeVisible();
    const buttonBox = (await cashback.boundingBox())!;
    const panelBox = (await initialPanel.boundingBox())!;
    if (width < 768) expect(panelBox.y).toBeGreaterThanOrEqual(buttonBox.y + buttonBox.height);
    else expect(panelBox.x).toBeGreaterThanOrEqual(buttonBox.x + buttonBox.width);

    await warranty.focus();
    await page.keyboard.press('Enter');
    await expect(warranty).toHaveAttribute('aria-expanded', 'true');
    await expect(cashback).toHaveAttribute('aria-expanded', 'false');
    await expect(guide.getByText(/cover beyond the original warranty/i)).toBeVisible();
    await gift.focus();
    await page.keyboard.press('Space');
    await expect(gift).toHaveAttribute('aria-expanded', 'true');
    await expect(warranty).toHaveAttribute('aria-expanded', 'false');
    await expect(guide.getByText(/extra item that may be offered/i)).toBeVisible();
    await expectReadable(gift, width);
    await expectReadable(guide.getByText(/extra item that may be offered/i), width);
    await expectReflow(page, width);
    if (width < 768) {
      await page.keyboard.press('Space');
      await expect(gift).toHaveAttribute('aria-expanded', 'false');
      await expect(guide.getByText(/extra item that may be offered/i)).toBeHidden();
      await page.setViewportSize({ width: 1280, height: 800 });
      await expect(gift).toHaveAttribute('aria-expanded', 'true');
      await expect(guide.getByText(/extra item that may be offered/i)).toBeVisible();
    }
    await page.keyboard.press('Space');
    await expect(gift).toHaveAttribute('aria-expanded', 'true');
    await expect(guide.getByText(/extra item that may be offered/i)).toBeVisible();
  });
}
