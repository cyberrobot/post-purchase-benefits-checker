"""Support installation evidence without changing existing requirement definitions."""

from alembic import op

revision = "0006_promotion_requirements"
down_revision = "0005_relative_claim_windows"
branch_labels = None
depends_on = None

LEGACY_TYPES = "'receipt','serial_number','registration','invoice','barcode','imei'"


def upgrade() -> None:
    op.drop_constraint("ck_requirements_type", "requirements", type_="check")
    op.create_check_constraint(
        "ck_requirements_type",
        "requirements",
        f"requirement_type IN ({LEGACY_TYPES},'installation_evidence')",
    )


def downgrade() -> None:
    # PostgreSQL validates existing rows while holding the DDL lock. If installation
    # evidence exists, adding the legacy check fails and transactional DDL restores
    # the PR-14 constraint and revision, without deleting or reinterpreting any data.
    op.drop_constraint("ck_requirements_type", "requirements", type_="check")
    op.create_check_constraint(
        "ck_requirements_type", "requirements", f"requirement_type IN ({LEGACY_TYPES})"
    )
