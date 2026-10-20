"""Explicit offline development/test reference import. Never invoked by startup."""

import argparse
import json
import sys
from dataclasses import asdict
from time import perf_counter

from pydantic import ValidationError
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.application.identity_matching import IdentityPersistenceError
from app.application.reference_data_import import (
    DATASET_ID,
    DATASET_SHA256,
    ReferenceDataConflict,
    import_reference_data,
    load_dataset,
)
from app.core.config import get_settings
from app.db.engine import create_database_engine
from app.db.repositories.reference_data_import import SqlAlchemyReferenceDataRepository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DATASET_ID, choices=[DATASET_ID])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--stage-promotions", action="store_true")
    args = parser.parse_args(argv)
    engine = None
    started = perf_counter()
    mode_name = "apply" if args.apply else "plan"
    entity_counts: dict[str, dict[str, int]] = {}

    def event(name: str, **fields: object) -> None:
        print(
            json.dumps(
                {
                    "event": name,
                    "dataset_id": args.dataset,
                    "dataset_version": 1,
                    "dataset_sha256": DATASET_SHA256,
                    "mode": mode_name,
                    "entity_counts": entity_counts,
                    "duration_ms": round((perf_counter() - started) * 1000, 3),
                    **fields,
                },
                sort_keys=True,
            )
        )

    try:
        if args.stage_promotions and not args.apply:
            raise ReferenceDataConflict("Promotion staging requires --apply")
        settings = get_settings()
        if settings.app_env == "production":
            raise ReferenceDataConflict("Reference import refuses APP_ENV=production")
        dataset = load_dataset(args.dataset)
        url = make_url(str(settings.database_url))
        print(
            json.dumps(
                {
                    "target": {
                        "host": url.host,
                        "port": url.port or 5432,
                        "database": url.database,
                    },
                    "mode": "apply" if args.apply else "plan",
                }
            )
        )
        event("reference_seed_plan")
        engine = create_database_engine(settings)
        with Session(engine) as session, session.begin():
            repository = SqlAlchemyReferenceDataRepository(session)
            if args.apply:
                repository.lock()
            else:
                session.connection().exec_driver_sql("SET TRANSACTION READ ONLY")
                session.connection().exec_driver_sql("SET LOCAL statement_timeout = '30s'")
            report = import_reference_data(
                repository, dataset, apply=args.apply, stage_promotions=args.stage_promotions
            )
        output = asdict(report)
        output["counts"] = {
            kind: {
                action: sum(e.kind == kind and e.action == action for e in report.entities)
                for action in ("create", "reuse")
            }
            for kind in sorted({e.kind for e in report.entities})
        }
        entity_counts.update(output["counts"])
        outcome = "noop" if report.no_op else "completed"
        print(
            json.dumps(
                {
                    **output,
                    "event": f"reference_seed_{outcome}",
                    "dataset_id": DATASET_ID,
                    "dataset_version": report.schema_version,
                    "dataset_sha256": report.semantic_sha256,
                    "mode": mode_name,
                    "entity_counts": entity_counts,
                    "duration_ms": round((perf_counter() - started) * 1000, 3),
                },
                sort_keys=True,
            )
        )
        return 0
    except ReferenceDataConflict as error:
        event("reference_seed_rejected", error_category="input_or_conflict")
        print(json.dumps({"error": "input_or_conflict", "message": str(error)}), file=sys.stderr)
        return 2
    except ValidationError:
        event("reference_seed_rejected", error_category="configuration_invalid")
        print(
            json.dumps(
                {"error": "configuration_invalid", "message": "Invalid loader configuration"}
            ),
            file=sys.stderr,
        )
        return 2
    except IntegrityError:
        event("reference_seed_rejected", error_category="conflict")
        print(
            json.dumps(
                {"error": "conflict", "message": "Database integrity conflict; run rolled back."}
            ),
            file=sys.stderr,
        )
        return 2
    except (SQLAlchemyError, IdentityPersistenceError) as error:
        category = _database_error_category(error)
        event("reference_seed_failed", error_category=category)
        print(
            json.dumps(
                {
                    "error": category,
                    "message": _database_error_message(category),
                }
            ),
            file=sys.stderr,
        )
        return 3
    except Exception:
        event("reference_seed_failed", error_category="operation_failed")
        print(
            json.dumps(
                {
                    "error": "operation_failed",
                    "message": "Reference import failed; transaction rolled back.",
                }
            ),
            file=sys.stderr,
        )
        return 3
    finally:
        if engine is not None:
            engine.dispose()


def _database_error_category(error: BaseException) -> str:
    """Classify common PostgreSQL failures without exposing driver diagnostics."""
    causes = list(_error_chain(error))
    sqlstates = {
        getattr(candidate, "sqlstate", None) or getattr(candidate, "pgcode", None)
        for candidate in causes
    }
    if sqlstates & {"3F000", "42P01", "42703", "42704"}:
        return "schema_mismatch"
    if any(isinstance(candidate, OperationalError) for candidate in causes) or any(
        isinstance(sqlstate, str) and sqlstate.startswith("08") for sqlstate in sqlstates
    ):
        return "database_unavailable"
    return "database_error"


def _error_chain(error: BaseException):
    """Return wrapped SQLAlchemy and driver exceptions without exposing their text."""
    pending = [error]
    seen = set()
    while pending:
        candidate = pending.pop()
        if id(candidate) in seen:
            continue
        seen.add(id(candidate))
        yield candidate
        if isinstance(candidate, DBAPIError):
            pending.append(candidate.orig)
        if candidate.__cause__ is not None:
            pending.append(candidate.__cause__)
        if candidate.__context__ is not None:
            pending.append(candidate.__context__)


def _database_error_message(category: str) -> str:
    if category == "schema_mismatch":
        return "Database schema is incompatible; run alembic upgrade head."
    if category == "database_unavailable":
        return "Database connection unavailable; check DATABASE_URL and PostgreSQL readiness."
    return "Database operation failed; details are omitted."


if __name__ == "__main__":
    raise SystemExit(main())
