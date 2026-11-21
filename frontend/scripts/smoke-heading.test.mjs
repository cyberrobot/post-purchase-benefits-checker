import assert from 'node:assert/strict';
import { assertHomepageHeading } from './smoke-heading.mjs';

test('checks the heading text independently of inline markup', () => {
  assert.doesNotThrow(() =>
    assertHomepageHeading('<main><h1>Find <span>benefits</span> from a purchase</h1></main>'),
  );
  assert.throws(() => assertHomepageHeading('<main></main>'));
  assert.throws(() => assertHomepageHeading('<main><h1>Find something else</h1></main>'));
  assert.throws(() => assertHomepageHeading('<h1 hidden>Find benefits from a purchase</h1>'));
  assert.doesNotThrow(() =>
    assertHomepageHeading('<h1>Find <span hidden>unwanted</span>benefits from a purchase</h1>'),
  );
});
