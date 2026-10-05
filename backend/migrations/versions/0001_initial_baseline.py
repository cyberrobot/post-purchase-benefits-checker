"""Create the initial empty schema baseline.

Revision ID: 0001_initial_baseline
Revises:
Create Date: 2026-10-05
"""

from collections.abc import Sequence

revision: str = "0001_initial_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No product-domain tables belong in the foundation migration."""


def downgrade() -> None:
    """The empty baseline has no schema objects to remove."""
