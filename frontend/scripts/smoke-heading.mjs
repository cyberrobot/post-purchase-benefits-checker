import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { parse } = require('next/dist/compiled/node-html-parser');

export function assertHomepageHeading(html) {
  const document = parse(html);
  for (const hidden of document.querySelectorAll('[hidden], [aria-hidden="true"]')) hidden.remove();
  const heading = document.querySelector('h1');
  assert.ok(heading, 'Homepage must contain an h1');
  assert.equal(heading.textContent.replace(/\s+/g, ' ').trim(), 'Find benefits from a purchase');
}
