"""Canonical public identity derived from the two persisted slugs."""

import re

SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"
PUBLIC_SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*--[a-z0-9]+(-[a-z0-9]+)*$"
SLUG_MAX_LENGTH = 255


def is_slug(value: str) -> bool:
    return len(value) <= SLUG_MAX_LENGTH and re.fullmatch(SLUG_PATTERN, value) is not None


def public_slug(manufacturer: str, promotion: str) -> str | None:
    if is_slug(manufacturer) and is_slug(promotion):
        return f"{manufacturer}--{promotion}"
    return None
