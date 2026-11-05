import { fireEvent, render, screen, within } from '@testing-library/react';
import { populatedClaim } from '@/lib/api/promotion.fixture';
import { resolved as rawResolved, unresolved as rawUnresolved } from '@/lib/api/fixtures';
import {
  checkPurchaseResponseSchema,
  type CheckPurchaseResponse,
} from '@/lib/api/eligibility.contract';
import {
  PurchaseCheckSessionProvider,
  usePurchaseCheckSession,
} from '../session/PurchaseCheckSession';
import { ResultsOverview } from './ResultsOverview';
import { calendarDate, statuses, type Promotion } from './presentation';
import { reasonLabels } from './explanations';
const resolved = checkPurchaseResponseSchema.parse(rawResolved);
const unresolved = checkPurchaseResponseSchema.parse(rawUnresolved);
const promotion = populatedClaim.outcome === 'resolved' ? populatedClaim.promotions[0] : null;
const purchase = {
  brand: 'My Brand',
  model: '<script>alert(1)</script>',
  retailer: 'My Shop',
  purchase_date: '2024-02-29',
  purchase_price: '999999999999.99',
};
function show(response: CheckPurchaseResponse) {
  function Setup() {
    const session = usePurchaseCheckSession();
    return (
      <>
        <button onClick={() => session.publish(purchase, response)}>Load</button>
        <ResultsOverview />
      </>
    );
  }
  render(
    <PurchaseCheckSessionProvider>
      <Setup />
    </PurchaseCheckSessionProvider>,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Load' }));
}
it('shows the exact purchase, all benefits, source verification and functional safe disclosures', () => {
  show(populatedClaim);
  expect(
    screen.getByRole('heading', { name: `${purchase.brand} · ${purchase.model}` }),
  ).toBeVisible();
  expect(screen.getByText('£999,999,999,999.99')).toBeVisible();
  expect(screen.getByText('29 Feb 2024')).toBeVisible();
  expect(screen.getByText('08 Oct 2026')).toBeVisible();
  const summary = screen.getByRole('region', { name: 'Checked purchase summary' });
  expect(summary).toHaveClass('wrap-anywhere');
  expect(within(summary).getByText('My Shop')).toHaveClass('wrap-anywhere');
  expect(within(summary).getByRole('link', { name: /Edit purchase details/ })).toHaveClass(
    'text-brand',
  );
  const card = screen.getByRole('article');
  expect(within(card).getByRole('heading', { name: '£10.00 cashback' })).toBeVisible();
  expect(within(card).getByRole('heading', { name: 'Percentage cashback' })).toBeVisible();
  expect(
    within(card).getByText('Provide the purchase price to calculate the cashback reward.'),
  ).toBeVisible();
  expect(within(card).getByText('02 Oct 2026').parentElement).toHaveTextContent('My Brand');
  const detailsButton = within(card).getByRole('button', { name: 'View Full Promotion Details' });
  expect(detailsButton).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(detailsButton);
  expect(within(card).getByText(/not an approved or paid claim/)).toBeVisible();
  expect(within(card).getByText(/Claim window opens/).parentElement).toHaveTextContent(
    '01 Oct 2026',
  );
  expect(within(card).getByText('Recorded rules').closest('details')).not.toHaveAttribute('open');
  for (const link of within(card).getAllByRole('link')) {
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener noreferrer'));
  }
  expect(document.querySelector('script')).toBeNull();
});
it('keeps six variants, five classifications and local zero-count filters with no status inference', () => {
  if (populatedClaim.outcome !== 'resolved') throw new Error('fixture');
  const promotions = [...statusCases, statusCases[2]].map((fixture, i) => ({
    ...promotion!,
    promotion_variant_id: `variant-${i}`,
    variant_name: `Variant ${i}`,
    claim_window: fixture.dates,
    eligibility: {
      ...promotion!.eligibility,
      classification: fixture.classification,
      reasons: fixture.reasons,
      rule_evaluations: fixture.rules,
      claim_window_status: fixture.timing,
    },
  }));
  show({ ...populatedClaim, promotions });
  expect(screen.getAllByRole('article')).toHaveLength(6);
  expect(screen.getByRole('button', { name: 'Not eligible (2)' })).toHaveAttribute(
    'aria-pressed',
    'false',
  );
  fireEvent.click(screen.getByRole('button', { name: 'Not eligible (2)' }));
  expect(screen.getAllByRole('article')).toHaveLength(2);
  expect(screen.getByRole('status')).toHaveTextContent('Showing 2 of 6');
  expect(screen.queryByText(/Recorded claim timing: Claim period open/)).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'All (6)' })).toBeVisible();
});
it('renders null and empty details honestly and zero filtered state can reset', () => {
  if (populatedClaim.outcome !== 'resolved') throw new Error('fixture');
  show({
    ...populatedClaim,
    promotions: [
      {
        ...promotion!,
        benefits: [],
        requirements: [],
        explanation: [],
        claim_window: null,
        eligibility: {
          ...promotion!.eligibility,
          claim_window_status: null,
          rule_evaluations: [],
          reasons: [],
        },
      },
    ],
  });
  expect(screen.getByText('No benefit details supplied.')).toBeVisible();
  expect(screen.getByText('Detailed reasons were not supplied.')).toBeVisible();
  expect(screen.getByText('No individual rule checks were supplied.')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'View Full Promotion Details' }));
  expect(screen.getByText(/The response lists no requirements/)).toBeVisible();
  expect(screen.queryByText(/Claim opens/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Not eligible (0)' }));
  expect(screen.getByRole('heading', { name: 'No results in this category' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Show all results' }));
  expect(screen.getAllByRole('article')).toHaveLength(1);
});
it.each(['not_found', 'ambiguous'] as const)(
  'shows field-specific %s guidance without candidate IDs',
  (status) => {
    if (unresolved.outcome !== 'unresolved_identity') throw new Error('fixture');
    show({
      ...unresolved,
      unresolved_identity: { field: 'model', status, candidate_ids: ['secret-id'] },
    });
    expect(screen.getByRole('heading', { name: 'Check your product model or SKU' })).toBeVisible();
    expect(
      screen.getByText(
        status === 'ambiguous'
          ? /More than one product model or sku matched/
          : /product model or sku could not be found/,
      ),
    ).toBeVisible();
    expect(screen.queryByText(/secret-id/)).not.toBeInTheDocument();
    expect(screen.queryByRole('article')).not.toBeInTheDocument();
  },
);
it('distinguishes published no-match from missing tab state', () => {
  show(resolved);
  expect(screen.getByRole('heading', { name: 'No matching published promotions' })).toBeVisible();
  expect(screen.queryByText('No results in this tab')).not.toBeInTheDocument();
});
it('wraps escaped long content and preserves non-cash benefits and unavailable reward reasons', () => {
  if (populatedClaim.outcome !== 'resolved' || !promotion) throw new Error('fixture');
  const longName = '<img src=x onerror=alert(1)>'.repeat(30);
  show({
    ...populatedClaim,
    promotions: [
      {
        ...promotion,
        promotion_name: longName,
        variant_name: 'Warranty variant',
        benefits: [
          {
            ...promotion.benefits[0],
            benefit_type: 'extended_warranty',
            name: 'Recorded extended cover',
            description: longName,
            cashback_reward_gbp: null,
            reward_unavailable_reason: 'reward_not_configured',
            reward_unavailable_explanation: null,
          },
          {
            ...promotion.benefits[0],
            benefit_id: 'second-benefit',
            benefit_type: 'free_gift',
            name: 'Recorded gift',
            cashback_reward_gbp: null,
            reward_unavailable_reason: null,
            reward_unavailable_explanation: null,
          },
        ],
        claim_window: null,
        eligibility: { ...promotion.eligibility, claim_window_status: null },
      },
    ],
  });
  expect(screen.getByRole('heading', { name: longName })).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Recorded extended cover' })).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Recorded gift' })).toBeVisible();
  expect(screen.queryByText('reward not configured')).not.toBeInTheDocument();
  expect(screen.queryByText('No monetary reward amount supplied.')).not.toBeInTheDocument();
  expect(document.querySelector('img')).toBeNull();
  expect(screen.queryByText(/£150|5-Year|Claim period open/)).not.toBeInTheDocument();
});

it('shows unavailable monetary reward wording for cashback without supplied details', () => {
  if (populatedClaim.outcome !== 'resolved' || !promotion) throw new Error('fixture');
  show({
    ...populatedClaim,
    promotions: [
      {
        ...promotion,
        benefits: [
          {
            ...promotion.benefits[0],
            cashback_reward_gbp: null,
            reward_unavailable_reason: null,
            reward_unavailable_explanation: null,
          },
        ],
      },
    ],
  });
  expect(screen.getByText('No monetary reward amount supplied.')).toBeVisible();
  expect(screen.queryByRole('heading', { name: '£10.00 cashback' })).not.toBeInTheDocument();
});

it('switches between cards and actual recorded rule rows while preserving filters and missing outcomes', () => {
  if (populatedClaim.outcome !== 'resolved' || !promotion) throw new Error('fixture');
  show({
    ...populatedClaim,
    promotions: [
      promotion,
      {
        ...promotion,
        promotion_variant_id: 'missing-rules',
        variant_name: 'Variant without evaluations',
        eligibility: {
          ...promotion.eligibility,
          rule_evaluations: [],
          classification: 'NOT_ELIGIBLE',
          reasons: [{ code: 'retailer_mismatch', rule_kind: 'retailer' }],
        },
      },
    ],
  });
  const matrix = screen.getByRole('button', { name: 'Rule Matrix' });
  expect(matrix).toHaveAttribute('aria-pressed', 'false');
  fireEvent.click(matrix);
  expect(matrix).toHaveAttribute('aria-pressed', 'true');
  expect(screen.queryByRole('article')).not.toBeInTheDocument();
  const table = screen.getByRole('table', { name: /Recorded rule matrix/ });
  expect(within(table).getAllByRole('row')).toHaveLength(3);
  expect(within(table).getByText('product: Recorded check passed')).toBeVisible();
  expect(
    within(table).getAllByText('No individual rule checks were supplied.').length,
  ).toBeGreaterThan(0);
  expect(within(table).getByText('Variant without evaluations')).toBeVisible();
  for (const rule of promotion.eligibility.rule_evaluations) {
    expect(
      within(table)
        .getAllByText(reasonLabels[rule.reason_code])
        .some((element) => !element.closest('details')),
    ).toBe(true);
  }
  fireEvent.click(screen.getByRole('button', { name: 'Not eligible (1)' }));
  expect(within(table).getAllByRole('row')).toHaveLength(2);
  fireEvent.click(screen.getByRole('button', { name: 'Cards' }));
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
  expect(screen.getAllByRole('article')).toHaveLength(1);
});

it('preserves the reported upcoming classification despite contradictory rule evidence and keeps details functional', () => {
  if (populatedClaim.outcome !== 'resolved' || !promotion) throw new Error('fixture');
  show({
    ...populatedClaim,
    promotions: [
      {
        ...promotion,
        eligibility: {
          ...promotion.eligibility,
          classification: 'CLAIM_NOT_YET_OPEN',
          claim_window_status: 'not_yet_open',
          rule_evaluations: [
            { kind: 'retailer', status: 'satisfied', reason_code: 'retailer_match' },
            { kind: 'purchase_price', status: 'unknown', reason_code: 'purchase_price_unknown' },
            {
              kind: 'purchase_date',
              status: 'not_satisfied',
              reason_code: 'purchase_date_before_start',
            },
          ],
        },
        claim_window: { status: 'not_yet_open', opens_on: '2026-11-27', deadline_on: '2026-12-31' },
        benefits: [
          { ...promotion.benefits[0], description: 'A long supplementary benefit description.' },
        ],
      },
    ],
  });
  const card = screen.getByRole('article');
  expect(within(card).getByText('Claim not yet open')).toBeVisible();
  expect(
    within(within(card).getByRole('region', { name: /Why this result\?/ })).getByText(
      statuses.find((status) => status.value === 'CLAIM_NOT_YET_OPEN')!.meaning,
    ),
  ).toBeVisible();
  expect(within(card).queryByText('Not eligible')).not.toBeInTheDocument();
  fireEvent.click(within(card).getByText('Recorded checks passed'));
  expect(within(card).getAllByText(reasonLabels.retailer_match)[0]).toBeVisible();
  expect(within(card).getAllByText(reasonLabels.purchase_price_unknown)[0]).toBeVisible();
  expect(within(card).getAllByText(reasonLabels.purchase_date_before_start)[0]).toBeVisible();
  expect(within(card).getByText('A long supplementary benefit description.')).not.toBeVisible();
  const guide = within(card).getByRole('button', { name: 'Claim Window Guide' });
  fireEvent.click(guide);
  expect(guide).toHaveAttribute('aria-expanded', 'true');
  expect(within(card).getByRole('region', { name: 'Claim window guide' })).toHaveTextContent(
    '27 Nov 2026',
  );
  expect(within(card).getByRole('region', { name: 'Claim window guide' })).toHaveTextContent(
    '31 Dec 2026',
  );
  fireEvent.click(within(card).getByRole('button', { name: 'View Full Promotion Details' }));
  expect(within(card).getByText('A long supplementary benefit description.')).toBeVisible();
  expect(within(card).getByRole('link', { name: /Official Portal Terms/ })).toHaveAttribute(
    'href',
    promotion.provenance.official_source_url,
  );
});

const passedRules: Promotion['eligibility']['rule_evaluations'] = [
  { kind: 'product', status: 'satisfied', reason_code: 'product_match' },
];
const statusCases: {
  classification: Promotion['eligibility']['classification'];
  reasons: Promotion['eligibility']['reasons'];
  rules: Promotion['eligibility']['rule_evaluations'];
  timing: Promotion['eligibility']['claim_window_status'];
  dates: Promotion['claim_window'];
  decisive: string;
}[] = [
  {
    classification: 'ELIGIBLE',
    reasons: [
      { code: 'all_configured_rules_satisfied', rule_kind: null },
      { code: 'claim_window_open', rule_kind: null },
    ],
    rules: passedRules,
    timing: 'open',
    dates: { status: 'open', opens_on: '2026-10-01', deadline_on: '2026-11-30' },
    decisive: reasonLabels.claim_window_open,
  },
  {
    classification: 'POTENTIALLY_ELIGIBLE',
    reasons: [
      { code: 'all_configured_rules_satisfied', rule_kind: null },
      { code: 'claim_window_unspecified', rule_kind: null },
    ],
    rules: passedRules,
    timing: null,
    dates: null,
    decisive: reasonLabels.claim_window_unspecified,
  },
  {
    classification: 'NOT_ELIGIBLE',
    reasons: [{ code: 'retailer_mismatch', rule_kind: 'retailer' }],
    rules: [{ kind: 'retailer', status: 'not_satisfied', reason_code: 'retailer_mismatch' }],
    timing: 'open',
    dates: null,
    decisive: reasonLabels.retailer_mismatch,
  },
  {
    classification: 'CLAIM_NOT_YET_OPEN',
    reasons: [
      { code: 'all_configured_rules_satisfied', rule_kind: null },
      { code: 'claim_window_not_yet_open', rule_kind: null },
    ],
    rules: passedRules,
    timing: 'not_yet_open',
    dates: { status: 'not_yet_open', opens_on: '2026-10-09', deadline_on: '2026-11-30' },
    decisive: reasonLabels.claim_window_not_yet_open,
  },
  {
    classification: 'EXPIRED',
    reasons: [
      { code: 'all_configured_rules_satisfied', rule_kind: null },
      { code: 'claim_window_expired', rule_kind: null },
    ],
    rules: passedRules,
    timing: 'expired',
    dates: { status: 'expired', opens_on: '2026-10-01', deadline_on: '2026-10-07' },
    decisive: reasonLabels.claim_window_expired,
  },
];
it.each(statusCases)(
  'shows coherent visible reasons and recorded dates for $classification',
  ({ classification, reasons, rules, timing, dates, decisive }) => {
    if (populatedClaim.outcome !== 'resolved') throw new Error('fixture');
    const status = statuses.find((item) => item.value === classification)!;
    show({
      ...populatedClaim,
      promotions: [
        {
          ...promotion!,
          claim_window: dates,
          eligibility: {
            ...promotion!.eligibility,
            classification,
            reasons,
            rule_evaluations: rules,
            claim_window_status: timing,
          },
        },
      ],
    });
    expect(within(screen.getByRole('article')).getByText(status.label)).toBeVisible();
    const explanation = screen.getByRole('region', { name: /Why this result\?/ });
    expect(within(explanation).getByRole('heading', { name: 'Why this result?' })).toBeVisible();
    expect(within(explanation).getByText(status.meaning)).toBeVisible();
    expect(within(explanation).getAllByText(decisive)[0]).toBeVisible();
    for (const other of statuses.filter((item) => item.value !== classification)) {
      expect(within(explanation).queryByText(other.meaning)).not.toBeInTheDocument();
    }
    const recordedTimingReason =
      timing === null ? 'claim_window_unspecified' : (`claim_window_${timing}` as const);
    for (const code of [
      'claim_window_open',
      'claim_window_not_yet_open',
      'claim_window_expired',
      'claim_window_unspecified',
    ] as const) {
      if (code !== recordedTimingReason)
        expect(within(explanation).queryByText(reasonLabels[code])).not.toBeInTheDocument();
    }
    if (classification === 'NOT_ELIGIBLE') {
      expect(
        within(explanation).queryByText(reasonLabels.all_configured_rules_satisfied),
      ).not.toBeInTheDocument();
    } else {
      expect(
        within(explanation).queryByRole('heading', { name: 'Conditions not met' }),
      ).not.toBeInTheDocument();
    }
    if (dates) {
      for (const value of [dates.opens_on, dates.deadline_on]) {
        expect(within(explanation).getByText(calendarDate(value))).toHaveAttribute(
          'dateTime',
          value,
        );
      }
      expect(
        within(explanation).queryByText('Opening and deadline dates were not supplied.'),
      ).not.toBeInTheDocument();
    } else {
      expect(
        within(explanation).getByText('Opening and deadline dates were not supplied.'),
      ).toBeVisible();
      expect(explanation.querySelector('time')).toBeNull();
    }
  },
);
it('keeps failed and unknown evidence separate and supplementary HTML escaped', () => {
  if (populatedClaim.outcome !== 'resolved') throw new Error('fixture');
  show({
    ...populatedClaim,
    promotions: [
      {
        ...promotion!,
        explanation: ['<img src=x onerror=alert(1)>'],
        eligibility: {
          ...promotion!.eligibility,
          classification: 'NOT_ELIGIBLE',
          reasons: [
            { code: 'retailer_mismatch', rule_kind: 'retailer' },
            { code: 'purchase_price_below_minimum', rule_kind: 'purchase_price' },
          ],
          rule_evaluations: [
            { kind: 'retailer', status: 'not_satisfied', reason_code: 'retailer_mismatch' },
            { kind: 'country', status: 'unknown', reason_code: 'country_unknown' },
            {
              kind: 'purchase_price',
              status: 'not_satisfied',
              reason_code: 'purchase_price_below_minimum',
            },
          ],
        },
      },
    ],
  });
  const explanation = screen.getByRole('region', { name: /Why this result\?/ });
  expect(within(explanation).getByRole('heading', { name: 'Conditions not met' })).toBeVisible();
  expect(
    within(explanation).getByRole('heading', { name: "Information we couldn't assess" }),
  ).toBeVisible();
  expect(
    within(explanation).getByText('These unknown facts are not the reason for this decision.'),
  ).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'View Full Promotion Details' }));
  expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Claim requirements' })).toBeVisible();
  expect(document.querySelector('img')).toBeNull();
});

it.each([
  ['NOT_ELIGIBLE', 'retailer_mismatch', 'retailer', 'Conditions not met'],
  ['POTENTIALLY_ELIGIBLE', 'country_unknown', 'country', "Information we couldn't assess"],
] as const)(
  'shows decisive %s reasons in the appropriate group when evaluations are unavailable',
  (classification, code, rule_kind, heading) => {
    if (populatedClaim.outcome !== 'resolved') throw new Error('fixture');
    show({
      ...populatedClaim,
      promotions: [
        {
          ...promotion!,
          eligibility: {
            ...promotion!.eligibility,
            classification,
            reasons: [{ code, rule_kind }],
            rule_evaluations: [],
          },
        },
      ],
    });
    const explanation = screen.getByRole('region', { name: /Why this result\?/ });
    const group = within(explanation).getByRole('heading', { name: heading }).parentElement!;
    expect(within(group).getByText('Decision reason')).toBeVisible();
    expect(within(group).getByText(reasonLabels[code])).toBeVisible();
    expect(within(explanation).getAllByText(reasonLabels[code])).toHaveLength(1);
    expect(within(explanation).getByText('No individual rule checks were supplied.')).toBeVisible();
  },
);

it.each([null, 'Shared variant'] as const)(
  'distinguishes explanations for variants named %s in Cards and Rule Matrix',
  (variantName) => {
    if (populatedClaim.outcome !== 'resolved') throw new Error('fixture');
    show({
      ...populatedClaim,
      promotions: [0, 1].map((index) => ({
        ...promotion!,
        promotion_name: 'Shared promotion',
        promotion_variant_id: `00000000-0000-0000-0000-00000000000${index + 7}`,
        variant_name: variantName,
      })),
    });
    for (const mode of ['Cards', 'Rule Matrix']) {
      fireEvent.click(screen.getByRole('button', { name: mode }));
      for (const index of [1, 2]) {
        const explanation = screen.getByRole('region', {
          name: `Shared promotion ${variantName ? `${variantName} ` : ''}Promotion result ${index} Why this result?`,
        });
        expect(explanation).toBeVisible();
        const heading = within(explanation).getByRole('heading', {
          name: 'Why this result?',
          level: 3,
        });
        const labelIds = explanation.getAttribute('aria-labelledby')!.split(' ');
        expect(labelIds).toContain(heading.id);
        for (const id of labelIds) expect(document.getElementById(id)).not.toBeNull();
      }
      expect(screen.getAllByRole('heading', { name: 'Shared promotion', level: 2 })).toHaveLength(
        2,
      );
      const ids = [...document.querySelectorAll('[id]')].map((element) => element.id);
      expect(new Set(ids).size).toBe(ids.length);
    }
  },
);

it('shows unknown rule reasons before later claim-timing reasons in backend order', () => {
  if (populatedClaim.outcome !== 'resolved') throw new Error('fixture');
  show({
    ...populatedClaim,
    promotions: [
      {
        ...promotion!,
        claim_window: null,
        eligibility: {
          ...promotion!.eligibility,
          classification: 'POTENTIALLY_ELIGIBLE',
          claim_window_status: null,
          reasons: [
            { code: 'purchase_price_unknown', rule_kind: 'purchase_price' },
            { code: 'claim_window_unspecified', rule_kind: null },
          ],
          rule_evaluations: [
            { kind: 'purchase_price', status: 'unknown', reason_code: 'purchase_price_unknown' },
          ],
        },
      },
    ],
  });
  const explanation = screen.getByRole('region', { name: /Why this result\?/ });
  const orderedText = explanation.textContent!;
  expect(orderedText.indexOf(reasonLabels.purchase_price_unknown)).toBeLessThan(
    orderedText.indexOf(reasonLabels.claim_window_unspecified),
  );
});
