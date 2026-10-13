# Samsung historical reference

`samsung-summer-wallet-cashback-2026.json` is reviewed local reference data, not a
candidate schema or a complete campaign catalogue. It covers **Galaxy Buds4 Pro
SM-R640 purchased directly from Samsung.com**, 3–23 June 2026, with exact GBP 50
cashback. Other campaign products and participating retailers need separate review.

## Evidence reviewed on 9 October 2026

| Manifest fact                                            | Official evidence                                                                                                                                                              |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Campaign, promoter and purchase dates                    | [Samsung PDF](https://api.my-samsung.com/UploadImages/terms/TermsConditionsLegal_91665.pdf), p. 1, clauses 1–2                                                                 |
| SM-R640 and GBP 50                                       | PDF p. 2, Table 1                                                                                                                                                              |
| Samsung.com participation                                | PDF p. 3, Table 2                                                                                                                                                              |
| New-only condition                                       | PDF pp. 1–2, clause 7                                                                                                                                                          |
| Proof of purchase; serial number/IMEI where requested    | PDF p. 4, clause 11                                                                                                                                                            |
| Claim destination and 30-day deadline                    | PDF pp. 1 and 4, clauses 11–12                                                                                                                                                 |
| Territory, age/company, resellers, prior claims and caps | PDF pp. 1 and 4, clauses 3–6 and 13                                                                                                                                            |
| Corroborating dates and Buds4 Pro GBP 50                 | [Samsung Newsroom, 15 June 2026](https://news.samsung.com/uk/samsung-electronics-uk-launches-summer-cashback-promotion-offering-up-to-300-cashback-on-selected-galaxy-devices) |

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

| Manifest fact                                                   | Official LG evidence                               |
| --------------------------------------------------------------- | -------------------------------------------------- |
| Purchase dates 21 May–24 June 2025                              | Summary; Eligibility §4                            |
| OLED55G54LW.AEK and GBP 150                                     | G5 Qualifying Products reward table, exact SKU row |
| LG.com/UK only                                                  | Eligibility §§3–4; Participating Retailers §22     |
| New UK variant; refurbished/second-hand exclusions              | Eligibility §4; General Conditions §27             |
| Readable serial number and full receipt/order confirmation      | Eligibility §§6–7                                  |
| Submission after purchase, inclusive 19 August 2025 deadline    | Eligibility §§4, 6, 9; Cashback Claim §12          |
| Processing/validation after 30 calendar days from purchase      | Eligibility §§4, 6; Cashback Claim §12             |
| Age, residency, GBP bank account, bulk and returns restrictions | Eligibility §§1–2, 10, 18–20; Cashback Claim §13   |

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

# Hisense Autumn Cashback 2026 reference

`hisense-autumn-cashback-2026-wf7i1248bbr.json` is a verified, bounded reference
for Hisense `WF7I1248BBR` purchased directly from Currys. It records GBP 100
cashback, purchase dates 9 September–27 October 2026 and claim dates 27 November–
24 December 2026, all inclusive. It is not a full campaign catalogue; absence of
other products and retailers does not establish campaign-wide ineligibility.

## Evidence status

The complete primary official terms, version 19 August 2026, were reviewed from
the attached 24-page Safari PDF print, including §§1–7, Annex 1 and Annex 2.
The manifest pins its SHA-256 and records the PDF's retrieval and review times.
The supporting Currys-hosted terms copy was compared for this model; its exact
retrieval time was not established and is left unset. The official terms name the
claim portal, but the portal itself was not independently accessed.

| Source                                                                                                                                         | Verified observation                                    | Outcome                                                                                 |
| ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| [Primary Hisense terms](https://uk.hisense.com/autumn-cashback-terms)                                                                          | §§3.1, 3.2, 3.5–3.7; §§4.1–4.8; §§5.1–5.12; Annexes 1–2 | Currys participation, model/reward, purchase and claim dates and requirements verified. |
| [Currys-hosted terms PDF](https://currysprod.a.bigcontent.io/v1/static/Hisense_Autumn_Cashback_2026_Promotion_-_Terms_and_Conditions_-_Currys) | Target model, amount and dates compared                 | Supporting only; primary 19 August terms govern; exact retrieval timestamp unavailable. |
| [Claim destination](https://autumncashback2026.hisensepromotions.co.uk/)                                                                       | URL stated in §§5.1 and 5.12                            | Portal availability and claim acceptance were not independently verified.               |

The terms require a valid receipt/proof of purchase and the product serial number.
They also limit claimants by residence, age, consumer use, employee status,
condition/returns, seller, offer combination and household claim count. The
five-field public request cannot evaluate those additional facts. The separate
May–June A-Rated campaign's GBP 150 reward is not evidence for this Autumn offer.

The fixture pins semantic facts and evidence status. The offline test-only
constructor creates a review graph in a caller-owned savepoint. It persists
verified primary HTML terms (`web_page`) provenance and the claim destination as cited by those
terms; the latter is explicitly not an assertion that the portal was accessed.
Sources are reused only when URL, type, title and timestamps all match exactly.
Tests publish through the persisted publication validation service. No
production seeding is provided.

Claimant, residency, age, consumer-use, condition, seller, return, offer-combination
and household restrictions are recorded as terms but are not inputs to eligibility.
The result describes recorded purchase rules only and does not guarantee claim
acceptance or payment; Hisense validates the claimant's evidence.

Normal tests consume local pinned observations and never fetch Hisense/Currys.
Integration tests verify the persisted publication path and HTTP eligibility
behaviour against the fixed claim window.
Run from `backend/` with Docker/Testcontainers available:

```sh
uv run pytest tests/unit/test_hisense_reference_promotion.py
uv run pytest tests/integration/test_hisense_reference_promotion.py
```

The Hisense claim source is also `web_page`, with the manifest's exact
`claim_source_title`. Its retrieval and verification timestamps record observation
and review of the URL in the captured official terms; they do not describe a
portal HTTP retrieval. The archived Safari PDF has separate capture metadata.

---

# Hotpoint Wren cashback 2026 reference

`hotpoint-wren-cashback-2026-h7ic16m6-uk.json` covers one MaxiSpace built-in
60 cm dishwasher, exact model `H7IC16M6 UK`, purchased directly from Wren.
Cashback is fixed GBP 75.00 regardless of optional purchase price. Purchases
must fall on 5 May–12 June 2026 inclusive; the base claim dates are 4 June–
4 December 2026 inclusive. This test-only reference is not a campaign catalogue.

**The 30-day wait after each purchase is unmodelled. Do not production-publish
this fixed-only fixture or make general claim-now promises.** The actual earliest
claim date is `max(2026-06-04, purchase_date + 30 calendar days)`, with a fixed
4 December deadline. The current candidate/persisted format accepts one fixed
or relative window; it cannot combine them. Its fixed-only `ELIGIBLE` result
may be a false positive during 4 June–11 July for purchases still waiting.
For 5 May purchases the first claim date is 4 June; for 12 June purchases it
is 12 July. Integrated eligible assertions use dates after the relevant wait.
The manifest's structured `claim_delay_limitation` is evidence metadata, is
included in the semantic pin, and is never passed into the strict v1 candidate.
The benefit description exposes this limitation through existing contracts.
A separate validated purchase-relative opening plus fixed absolute deadline
feature is required before general production publication.

## Evidence ledger

Implementation reviewed official page text on 12 October 2026; the UTC observation
and review completion timestamp is `2026-10-12T16:18:12Z`. These timestamps record
retrieval of web-tool page text, whose reported crawl ages were three days for
terms, six days for FAQ and today for the campaign page. They do not assert a
fresh origin-server retrieval or an exact HTML-byte checksum/revision.

| Source                                                                   | Observations                                                                                                                                                                                                                       |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Official Wren terms](https://promo.hotpoint.co.uk/terms-and-conditions) | Only the `HOTPOINT CASHBACK PROMOTION - WREN` subsection: clauses 2/3 dates, clause 4 dishwasher model and GBP 75, clause 13 Wren, clauses 5/6/8 receipt, serial, warranty and wait, clauses 1/9/14/15/16/20 restrictions/payment. |
| [Official campaign claim destination](https://promo.hotpoint.co.uk/)     | Campaign page corroborates Wren's 4 December deadline; no claim submitted or user-specific claim acceptance checked. Wren clause 8(c) names `hotpoint.co.uk/promo`; this manifest uses the reviewed official campaign destination. |
| [Official FAQ](https://promo.hotpoint.co.uk/faqs/)                       | Supporting corroboration of Wren extended deadline and 30-day wait.                                                                                                                                                                |

The adjacent participating-retailers and Hotpoint.co.uk-only subsections use
26 July deadlines and different scopes. They are excluded from Wren authority.
Receipt, serial number and warranty registration requirements are claim steps,
not proof that a customer satisfied them. Residence, age, employee exclusions,
condition, seller, prior claims, returns, offer combination, receipt quality and
bank details remain outside the five-field request. Date-only results do not
establish precise 00:00/23:59 cutoffs. Hotpoint alone decides claim approval.

`tests.hotpoint_reference.construct_reference(session)` is offline and test-only.
It rejects pending caller changes, builds within a caller-owned savepoint in
`review`, uses canonical identities and the existing candidate preflight, and
leaves commit/publication ownership to the test caller. Tests use the persisted
`change_promotion_status` gate; unresolved candidate references are not publication
approval. Safe review/active/expired replay preserves the graph and lifecycle;
conflicts fail without replacement. Shared identity resolution, source verification, and graph fingerprinting helpers live in tests/reference_helpers.py and are used by both the Hotpoint and Hisense reference fixtures.
Only verified `primary` and `claim` sources are persisted; the FAQ remains
supporting evidence. No startup seed, migration, public contract, network test,
personal receipt, genuine serial or banking information is added.

Run from `backend/` with the existing migrated PostgreSQL Testcontainer:

```sh
uv run pytest tests/unit/test_hotpoint_reference_promotion.py
uv run pytest tests/integration/test_hotpoint_reference_promotion.py
```

## Sony BRAVIA Autumn Cashback 2026 — test reference only

`sony-bravia-autumn-cashback-2026-k55xr75m2b.json` pins one exact TV model,
**K55XR75M2B (55-inch BRAVIA 7 II)**, purchased directly from **Currys - UK**
from **30 September through 27 October 2026**, for **GBP 150.00** cashback.
`K55XR75M2PB` is a distinct model; no other model or retailer is assessed.
The observed Sony dealer label remains `Currys - UK` in the pinned evidence.
Construction uses shared canonical `Currys` (also used by Hisense) and a curated
`RetailerAlias` for `Currys - UK`; both input names match the same ID. Conflicting
or ambiguous owners fail without merging or renaming records. Cleanup tracks newly
created aliases and preserves shared Hisense/Currys data.
`tests.sony_reference` validates the complete local JSON semantic SHA-256 before
writes and constructs only a review-state graph in the caller's savepoint.
Activation occurs through the existing persisted publication gate in isolated
PostgreSQL tests. Replays preserve identical review/active/expired records;
fixture cleanup deletes only rows it created.

Evidence was observed and reviewed on 13 October 2026 at the UTC times recorded
in the manifest. These are observations of official source text supplied by the
web tool, not origin-server retrieval timestamps or hashes of remote PDF bytes.
The semantic pin covers the whole manifest, including evidence and limitations.

| Fact | Official evidence |
| --- | --- |
| Exact model and GBP 150.00 | [Sony terms PDF](https://campaign.odw.sony-europe.com/redemption/terms/UK_TV_Autumn_Terms_and_Conditions_2026.pdf), version 26/08/2026, section 6, page 1 model row |
| Purchase period | Terms sections 5–6 |
| Currys - UK participant | [UK dealer PDF](https://campaign.odw.sony-europe.com/redemption/dealers/UK_TV_Autumn_dealers_2026.pdf), version 28/09/2026, page 3; terms section 11 |
| Individual 35-day wait | Terms section 8; [campaign page](https://www.sony.co.uk/cashback/braviaautumn2026) and [Sony FAQ](https://www.sony.co.uk/electronics/support/articles/00412189) |
| Final claim deadline | Terms section 10: 31 December 2026, subject to exact late-day CET cutoff |
| Account and destination | Terms section 7: My Sony account and official campaign URL |
| Receipt and serial photos | Terms section 9; order date controls where different |
| Original consumer, age, condition and returns | Terms sections 2–3 and 11–12 |
| One claim per model, two total | Terms section 13; conflicting FAQ wording does not override official terms |

The persisted sources are a verified `primary` terms PDF, verified `claim`
campaign web page and a separately versioned `supporting` dealer PDF. Each source
uses its documented observation times; the supporting PDF uses its own metadata
even when its recorded times equal the terms/page times. A pure mapping validates
aware, ordered timestamps for all roles. Tests use deliberately different
**synthetic** timestamps to prove mapping/reuse; recorded observations and the
semantic digest remain unchanged. Inspecting
the claim destination is not evidence that a customer submitted or received a
claim. Unlisted third-party or Currys Marketplace sellers are not assumed authorised.
Receipt and serial-number requirements describe the screen serial/device-ID
photo **or** back-label model/manufacturing-date/serial photo alternatives.
My Sony account creation remains explanatory text; no purchased-TV registration
requirement is inferred.

**Production publication is blocked.** The current backend supports a fixed
claim window OR a purchase-relative window, and cannot enforce both the
individual opening `max(2026-11-04, purchase_date + 35 calendar days)` and the
fixed 31 December deadline. The persisted **base window** is 4 November through
31 December only. For a 27 October purchase, the first legal calendar claim day
is **1 December**, so the engine could produce false-positive `ELIGIBLE` results
from 4–30 November. The structured `claim_delay_limitation` is pinned evidence
metadata, not an executable runtime rule. Integrated eligible assertions use
safe dates only. A separate combined-window feature is required before production use.

The five-field API cannot prove age, first ownership, new condition, country/seller,
returns, prior claims, My Sony account, receipt validity, actual serial/photos or
payment eligibility. UK date-only evaluation does not enforce the exact CET
minute cutoff. Sony retains final approval authority; results are not claim guarantees.
No network request, account credentials, receipt, personal serial or production seed
is involved in normal tests.

```sh
uv run pytest tests/unit/test_sony_reference_promotion.py
uv run pytest tests/integration/test_sony_reference_promotion.py
```
