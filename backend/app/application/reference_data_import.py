"""Offline catalogue planning over an application-owned persistence port."""

import hashlib
import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domain.identity_normalisation import normalise_identifier, normalise_text

DATASET_ID = "mvp-reviewed-v1"
# Reviewed semantic digest; amendments require explicit review and a new version.
DATASET_SHA256 = "719c1d3fd699cc0eecefa4a49c64ee5572bcaf0916f0fd9f6334c2daf8a6d3a4"


class ReferenceDataConflict(ValueError):
    """Safe validation or persisted fact conflict."""


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    manufacturer: str = Field(min_length=1, max_length=255)
    manufacturer_slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=255)
    retailer: str = Field(min_length=1, max_length=255)
    retailer_slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=255)
    retailer_alias: str | None = Field(default=None, min_length=1, max_length=255)
    product: str = Field(min_length=1, max_length=255)
    product_slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=255)
    model: str = Field(min_length=1, max_length=255)
    manifest: str = Field(pattern=r"^[a-z0-9-]+\.json$", max_length=255)
    semantic_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    dataset_id: str
    schema_version: int
    facts: list[Fact] = Field(min_length=5, max_length=5)


def semantic_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _bounded_json(raw: bytes) -> object:
    if len(raw) > 65536:
        raise ReferenceDataConflict("Reference file exceeds size limit")
    try:

        def unique_object(pairs):
            result = {}
            for key, item in pairs:
                if key in result:
                    raise ValueError("Duplicate JSON key")
                result[key] = item
            return result

        value = json.loads(raw, object_pairs_hook=unique_object)

        def check(item: object, depth: int = 0) -> None:
            if depth > 12:
                raise ValueError
            if isinstance(item, dict):
                if len(item) > 100:
                    raise ValueError
                for child in item.values():
                    check(child, depth + 1)
            elif isinstance(item, list):
                if len(item) > 100:
                    raise ValueError
                for child in item:
                    check(child, depth + 1)
            elif isinstance(item, str) and len(item) > 8192:
                raise ValueError

        check(value)
        return value
    except (ValueError, TypeError, RecursionError):
        raise ReferenceDataConflict("Invalid bounded reference JSON") from None


def load_dataset(dataset_id: str = DATASET_ID) -> Dataset:
    if dataset_id != DATASET_ID:
        raise ReferenceDataConflict("Unknown bundled dataset")
    try:
        pack = files("app.data.reference")
        value = _bounded_json(pack.joinpath("dataset.json").read_bytes())
        if semantic_hash(value) != DATASET_SHA256:
            raise ReferenceDataConflict("Dataset semantic digest mismatch")
        dataset = Dataset.model_validate(value)
        if dataset.dataset_id != DATASET_ID or dataset.schema_version != 1:
            raise ReferenceDataConflict("Unsupported dataset version")
        makers, models = set(), set()
        for fact in dataset.facts:
            maker = normalise_text(fact.manufacturer)
            model = (maker, normalise_identifier(fact.model))
            if maker in makers or model in models:
                raise ReferenceDataConflict("Duplicate normalized catalogue identity")
            makers.add(maker)
            models.add(model)
            manifest = _bounded_json(pack.joinpath(fact.manifest).read_bytes())
            if semantic_hash(manifest) != fact.semantic_sha256:
                raise ReferenceDataConflict(
                    f"{fact.manufacturer}: manifest semantic digest mismatch"
                )
            if (
                manifest["manufacturer"] != fact.manufacturer
                or manifest["product"] != {"name": fact.product, "model_or_sku": fact.model}
                or manifest["retailer"] != (fact.retailer_alias or fact.retailer)
                or manifest["reference_version"] != 1
                or (
                    fact.manufacturer not in {"Samsung", "LG"}
                    and manifest.get("evidence_status") != "verified"
                )
            ):
                raise ReferenceDataConflict("Catalogue evidence mismatch")
        return dataset
    except (OSError, ValidationError, KeyError, TypeError, ValueError) as error:
        if isinstance(error, ReferenceDataConflict):
            raise
        raise ReferenceDataConflict("Invalid bundled reference dataset") from None


@dataclass(frozen=True)
class PlannedEntity:
    kind: str
    key: str
    action: str


@dataclass(frozen=True)
class ImportReport:
    dataset_id: str
    schema_version: int
    semantic_sha256: str
    mode: str
    entities: tuple[PlannedEntity, ...]
    staged_promotions: int = 0
    reused_promotions: int = 0
    published_promotions: int = 0
    no_op: bool = False


class ReferenceDataRepository(Protocol):
    def catalogue(self, dataset: Dataset, *, apply: bool) -> tuple[PlannedEntity, ...]: ...
    def preview_promotions(self, dataset: Dataset) -> tuple[PlannedEntity, ...]: ...
    def stage(self, dataset: Dataset) -> tuple[int, int]: ...


def import_reference_data(
    repository: ReferenceDataRepository,
    dataset: Dataset,
    *,
    apply: bool = False,
    stage_promotions: bool = False,
    preview_promotions: bool = False,
) -> ImportReport:
    if preview_promotions and apply:
        raise ReferenceDataConflict("Promotion preview requires read-only plan mode")
    if stage_promotions and not apply:
        raise ReferenceDataConflict("Promotion staging requires --apply")
    if semantic_hash(dataset.model_dump()) != DATASET_SHA256:
        raise ReferenceDataConflict("Unapproved dataset facts")
    # The complete read-only plan must succeed before any mutation.
    entities = repository.catalogue(dataset, apply=False)
    if preview_promotions or stage_promotions:
        entities += repository.preview_promotions(dataset)
    created = reused = 0
    if apply:
        repository.catalogue(dataset, apply=True)
        if stage_promotions:
            created, reused = repository.stage(dataset)
    return ImportReport(
        dataset.dataset_id,
        dataset.schema_version,
        DATASET_SHA256,
        "apply" if apply else "plan",
        entities,
        created,
        reused,
        no_op=apply and created == 0 and all(entity.action == "reuse" for entity in entities),
    )
