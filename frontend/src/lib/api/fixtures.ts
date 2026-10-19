// Deterministic transport fixtures only; never imported by application UI.
export const purchase = {
  brand: 'Example',
  model: 'SKU-1',
  retailer: 'Shop',
  purchase_date: '2026-10-01',
  purchase_price: '799.99',
};
export const requestId = '00000000-0000-0000-0000-000000000009';
export const resolved = {
  outcome: 'resolved',
  evaluation_date: '2026-10-08',
  resolved_identity: { manufacturer_id: requestId, retailer_id: requestId, product_id: requestId },
  promotions: [],
  no_match_reason: 'no_matching_published_promotions',
  explanation: ['No matching promotion.'],
};
export const unresolved = {
  outcome: 'unresolved_identity',
  evaluation_date: '2026-10-08',
  unresolved_identity: { field: 'brand', status: 'not_found', candidate_ids: [] },
  explanation: ['Brand not found.'],
};
export const problem = {
  type: 'about:blank',
  title: 'Invalid request',
  status: 422,
  detail: 'Provide valid purchase fields.',
  code: 'invalid_purchase_request',
  request_id: requestId,
};
