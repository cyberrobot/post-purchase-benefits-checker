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

# LG historical G5 reference

`lg-g5-cashback-2025.json` covers one exact UK model **OLED55G54LW.AEK**,
purchased directly from **LG.com/UK**, between **21 May and 24 June 2025**,
with **GBP 150.00** cashback. It is not the full LG G5 campaign catalogue;
other models and rewards in the official G5 table require separate reviewed data.

## LG evidence reviewed on 9 October 2026

The [official LG UK G5 terms](https://www.lg.com/uk/tncs/g5-cashback/)
were opened and inspected during implementation at **10:37:50 UTC**. Retrieval
and verification record that observed instant; they are not inferred from the
historical purchase dates. The claim source records the destination named in
those terms, [lgcashback.com/g5](https://www.lgcashback.com/g5), and explicitly
states that the portal was not accessed. Live accessibility and claim acceptance
have not been independently established.

| Manifest fact | Official LG evidence |
| --- | --- |
| Purchase dates 21 May–24 June 2025 | Summary; Eligibility §4 |
| OLED55G54LW.AEK and GBP 150 | G5 Qualifying Products reward table, exact SKU row |
| LG.com/UK only | Eligibility §§3–4; Participating Retailers §22 |
| New UK variant; refurbished/second-hand exclusions | Eligibility §4; General Conditions §27 |
| Readable serial number and full receipt/order confirmation | Eligibility §§6–7 |
| Submission after purchase, inclusive 19 August 2025 deadline | Eligibility §§4, 6, 9; Cashback Claim §12 |
| Processing/validation after 30 calendar days from purchase | Eligibility §§4, 6; Cashback Claim §12 |
| Age, residency, GBP bank account, bulk and returns restrictions | Eligibility §§1–2, 10, 18–20; Cashback Claim §13 |

The **fixed inclusive submission window is 21 May–19 August 2025**. Consumers
can register on the purchase date; the 30-day processing/validation delay does
not delay the claim opening. The terms' **23:59 GMT** cutoff is represented only
at calendar-date resolution. The current fixed-window contract cannot enforce
submission after each individual's purchase, so service regression dates are
always on or after the supplied purchase date.

## LG construction, checks and limits

`tests/lg_reference.py` mirrors the bounded Samsung constructor with an
independently pinned semantic manifest. It preserves the exact `.AEK` suffix,
resolves unambiguous existing identities and rejects conflicting/ambiguous
identity or graph data. Product display names may differ when a canonical model
and manufacturer precisely match. A shortened model is not automatically an
alias for this UK variant. JSON key order/formatting do not affect the digest;
any change to facts, evidence, requirements or limitations requires a deliberate
new review and digest update.

The helper constructs in a caller-owned savepoint, performs the existing
UUID-based candidate preflight, and publishes only through the persisted
`review → active` validation gate before expiring through the lifecycle service.
The official page and its designated claim destination use distinct source
records, both `web_page`, with meaningful source verification titles. Failed
construction rolls back its writes; replay from review/active completes expiry,
and expired replay compares the graph without reactivation. The integration
fixture deletes only rows it created, preserving reused shared identities and
pre-existing sources.

Migrated PostgreSQL tests exercise real purchase snapshots, every purchase/claim
boundary, exact fixed cashback with/without purchase price, publication rejection,
atomic rollback, identity aliases/conflicts, read-only reproducibility and the
existing HTTP route. Synthetic unlinked model and unrelated retailer rows are
separate from official facts; their resolved no-match results do not establish
whether a different real G5 model qualifies for LG's full campaign. Unknown
identities and an unreviewed shortened model stay unresolved. Normal tests use
local data and never request the LG URLs.

Run from `backend/` with Docker available:

```sh
uv run pytest tests/unit/test_lg_reference_promotion.py
uv run pytest tests/integration/test_lg_reference_promotion.py
```

The stored historical lifecycle is `expired`, while a historical check during
the claim window can return computed `ELIGIBLE`. That result describes configured
rules only. The v1 request cannot establish claimant age/residency, GBP bank
account, new condition, prior claims, returns, purchase-volume cap or seller
details. Evidence requirements are instructions, not proof they were met. A pure
domain test checks refurbished/unknown condition without claiming that the
public request enforces condition. LG alone approves claims; no approval or
payment guarantee, minute-level cutoff enforcement, production data deployment,
startup seeding, schema migration, new configuration or API/MCP change is added.
changes are introduced. Normal startup does not load this historical reference.

---

# Hisense Autumn 2026 review candidate (publication blocked)

`hisense-autumn-cashback-2026-wf7i1248bbr.json` is **not verified reference data**.
It records a bounded proposal for model `WF7I1248BBR` at Currys and the facts
specified for investigation. Those dates, the GBP 100 amount, Currys participation,
claim destination and requirements remain unverified. The candidate constructor
keeps the graph in `review`, records unverified sources without verification
timestamps, and the persisted publication gate must reject activation. It must not
be used to claim the active purchase-check behaviour in PR 22's objective.

## Evidence audit on 9 October 2026

| Source | Observation | What it establishes |
| --- | --- | --- |
| [Hisense Autumn terms and conditions](https://autumncashback2026.hisensepromotions.co.uk/en_gb/terms-and-conditions-promotion/?country_promotion=2) | Opened; page returned a JavaScript/bot verification challenge | Nothing about applicable terms or Annexes 1/2 was verified |
| [Hisense UK campaign page](https://uk.hisense.com/promotions-giveaways/energy-efficiency-cashback) | Not accessible in the review environment | Nothing directly verified |
| [Currys product page](https://www.currys.co.uk/products/hisense-kitchenfit-7i-series-wf7i1248bbr-wifienabled-12-kg-1400-spin-washing-machine-black-10304682.html) | Opened; product identity is shown and page advertises “up to £300” on selected Hisense appliances | Product identity only; not Autumn retailer annex, exact reward, or dates |
| [Hisense-designated claim portal](https://autumncashback2026.hisensepromotions.co.uk/) | Not independently reviewed | Availability and claim acceptance unknown |

No retrieval/verification timestamp is fabricated for the challenged terms or
unavailable manufacturer page. The Currys observation timestamp is approximate to
the minute from the review session and is retrieval only, not verification. The
different May–June 2026 A-Rated promotion's reported GBP 150 amount is explicitly
excluded from this candidate.

The complete applicable official Autumn terms, including participating retailers,
qualifying model/reward annexes, restrictions, claim dates and evidence requirements,
must be obtained and reviewed before the digest, evidence ledger, graph sources or
tests are upgraded to a verified reference. Until then there is no active Hisense
promotion and no Hisense eligibility claim. The five-field request also cannot
evaluate claimant identity, region, age, product condition, third-party seller,
serial/proof submission, previous claims or payment details.
