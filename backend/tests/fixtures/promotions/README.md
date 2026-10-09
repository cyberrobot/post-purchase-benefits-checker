# Samsung historical reference

`samsung-summer-wallet-cashback-2026.json` is reviewed local reference data, not a
candidate schema or a complete campaign catalogue. It covers **Galaxy Buds4 Pro
SM-R640 purchased directly from Samsung.com**, 3–23 June 2026, with exact GBP 50
cashback. Other campaign products and participating retailers need separate review.

## Evidence reviewed on 9 October 2026

| Manifest fact | Official evidence |
| --- | --- |
| Campaign, promoter and purchase dates | [Samsung PDF](https://api.my-samsung.com/UploadImages/terms/TermsConditionsLegal_91665.pdf), p. 1, clauses 1–2 |
| SM-R640 and GBP 50 | PDF p. 2, Table 1 |
| Samsung.com participation | PDF p. 3, Table 2 |
| New-only condition | PDF pp. 1–2, clause 7 |
| Proof of purchase; serial number/IMEI where requested | PDF p. 4, clause 11 |
| Claim destination and 30-day deadline | PDF pp. 1 and 4, clauses 11–12 |
| Territory, age/company, resellers, prior claims and caps | PDF pp. 1 and 4, clauses 3–6 and 13 |
| Corroborating dates and Buds4 Pro GBP 50 | [Samsung Newsroom, 15 June 2026](https://news.samsung.com/uk/samsung-electronics-uk-launches-summer-cashback-promotion-offering-up-to-300-cashback-on-selected-galaxy-devices) |

The official PDF and Newsroom were opened and checked during implementation.
Retrieval is recorded to minute precision at 09:42 UTC; subsequent verification
was completed at 09:42:53 UTC. These are evidence review times, not purchase dates.
The [claim destination](https://samsungoffers.claims/walletcashback2026) was verified
**from the official PDF**, without visiting the portal. Its source title records
that distinction. Current portal accessibility and acceptance of claims are unknown.

The purchase day is day 1. Relative inclusive offsets **0..29** yield 3 June →
2 July and 23 June → 22 July, consistent with clause 12's final 22 July 23:59 BST
deadline. A fixed 22 July window would incorrectly extend earlier purchases.

## Construction and replay

`tests/samsung_reference.py` is a test-only constructor using the existing ORM.
It resolves canonical names/model/SKU through existing normalisation and aliases,
creates only missing identities, and rejects ambiguous or conflicting facts.
There are no committed authoritative UUIDs. SM-R640 is the canonical model number;
no unverified Samsung.com retailer-specific SKU is invented.

A semantic SHA-256 pin protects **all** version 1 facts, evidence and limitations.
JSON whitespace and object key order do not matter. Any semantic edit requires
renewed evidence review and a deliberate digest update in the helper. Malformed,
missing, extra or altered data are rejected rather than repaired.

The caller owns an atomic graph transaction. After graph construction, the helper
parses the canonical UUID-based `CandidatePromotionV1` contract and checks its
preflight issues. Preflight intentionally retains `unresolved_references` and
cannot approve publication. Only the existing persisted publication gate performs
`review → active`; a subsequent lifecycle transition finishes at `expired`.
Primary PDF, claim destination and supporting Newsroom are three distinct source
records. The PDF is not linked again as `terms`, because source links have a
composite promotion/source primary key.

Repeated construction compares every reference graph fact and source evidence,
returns the same record without edits, and fails on conflicts. Retry after review
or active completes expiration; an expired replay does not reactivate. Tests cover
rollback during construction, publication rejection, retirement and replay while
preserving provenance. The helper is scoped to isolated sequential test fixtures;
there is no operator loader or concurrent import service.

Run from `backend/` with Docker available:

```sh
uv run pytest tests/unit/test_samsung_reference_promotion.py
uv run pytest tests/integration/test_samsung_reference_promotion.py
```

The integration fixture uses migrated PostgreSQL through Testcontainers and the
actual read-only repeatable-read `purchase_check_snapshot` + `check_purchase` path,
including the existing HTTP route with an injected historical evaluation date.
Fake excluded retailer/model identities are separate test rows, not official
campaign entries. Tests never fetch the stored Samsung URLs. Testcontainers' own
Docker/container traffic is infrastructure, not manufacturer retrieval.

## Meaning and limits

`ELIGIBLE` means the currently configured manufacturer, product, retailer, purchase
dates and claim window match. Samsung alone approves claims. The five-field input
cannot establish new/unused condition, territory, age/company eligibility,
reseller/marketplace seller status, prior claims, household/company caps, or account
and Wallet steps. Requirements are instructions, not proof that they were met.
These limits appear in the persisted cashback description and manifest.

A separate pure domain test demonstrates refurbished → `NOT_ELIGIBLE` and missing
condition → `POTENTIALLY_ELIGIBLE`; it does not claim that the persisted v1 reference
or public request checks condition. Wrong known retailer/model and outside purchase
dates produce resolved **no matching published promotion**, whereas unknown
identities remain unresolved. Historical lifecycle `expired` preserves the graph
and permits an `ELIGIBLE` result for an explicitly historical date inside the claim
window. On 9 October 2026 its computed claim status is `EXPIRED`.

No startup seeding, migrations, production writes, configuration or API/MCP contract
changes are introduced. Normal startup does not load this historical reference.
