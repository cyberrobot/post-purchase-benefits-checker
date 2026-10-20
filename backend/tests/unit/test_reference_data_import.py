"""Bounded offline dataset and operator command contracts."""

import json
from contextlib import nullcontext
from dataclasses import asdict
from unittest.mock import Mock, call

import pytest
from pydantic import ValidationError

from app.application.reference_data_import import (
    DATASET_SHA256,
    Fact,
    ReferenceDataConflict,
    _bounded_json,
    import_reference_data,
    load_dataset,
    semantic_hash,
)
from app.cli.seed_reference_data import main
from app.core.config import Settings
from app.domain.identity_normalisation import normalise_identifier, normalise_text


def test_exact_approved_pack_and_semantic_pin():
    dataset = load_dataset()
    assert semantic_hash(dataset.model_dump()) == DATASET_SHA256
    assert [(f.manufacturer, f.model, f.retailer) for f in dataset.facts] == [
        ("Samsung", "SM-R640", "Samsung.com"),
        ("LG", "OLED55G54LW.AEK", "LG.com/UK"),
        ("Hisense", "WF7I1248BBR", "Currys"),
        ("Hotpoint", "H7IC16M6 UK", "Wren"),
        ("Sony", "K55XR75M2B", "Currys"),
    ]
    assert dataset.facts[-1].retailer_alias == "Currys - UK"
    assert normalise_text("ＳＡＭＳＵＮＧ") == "samsung"
    assert normalise_identifier(dataset.facts[1].model) == "oled55g54lw.aek"
    assert normalise_identifier(dataset.facts[3].model) == "h7ic16m6uk"


@pytest.mark.parametrize("value", ["../dataset", "https://example.com", "/tmp/data", "*"])
def test_only_allowlisted_dataset(value):
    with pytest.raises(ReferenceDataConflict):
        load_dataset(value)


@pytest.mark.parametrize("raw", [b"{", b" " * 65537, b"[" * 14 + b"0" + b"]" * 14])
def test_bounded_json(raw):
    with pytest.raises(ReferenceDataConflict):
        _bounded_json(raw)


def test_strict_schema_and_unapproved_fact_rejected():
    fact = load_dataset().facts[0].model_dump()
    with pytest.raises(ValidationError):
        Fact.model_validate({**fact, "retailer_sku": "invented"})
    with pytest.raises(ValidationError):
        Fact.model_validate({**fact, "model": 123})
    dataset = load_dataset().model_copy(update={"schema_version": 2})
    repository = Mock()
    with pytest.raises(ReferenceDataConflict, match="Unapproved"):
        import_reference_data(repository, dataset, apply=True)
    repository.catalogue.assert_not_called()


def test_plan_is_deterministic_and_has_no_writes():
    repository = Mock()
    repository.catalogue.return_value = ()
    first = import_reference_data(repository, load_dataset())
    second = import_reference_data(repository, load_dataset())
    assert asdict(first) == asdict(second)
    assert first.mode == "plan" and first.published_promotions == 0
    assert repository.catalogue.call_args.kwargs == {"apply": False}
    repository.stage.assert_not_called()


def test_staging_requires_apply():
    repository = Mock()
    with pytest.raises(ReferenceDataConflict, match="--apply"):
        import_reference_data(repository, load_dataset(), stage_promotions=True)
    repository.catalogue.assert_not_called()
    assert main(["--stage-promotions"]) == 2


def test_production_refused_before_engine_creation(monkeypatch, capsys):
    from app.cli import seed_reference_data as cli

    monkeypatch.setattr(
        cli,
        "get_settings",
        lambda: Settings(
            app_env="production",
            database_url="postgresql+psycopg://secret:password@localhost/db?secret=value",
        ),
    )
    engine = Mock()
    monkeypatch.setattr(cli, "create_database_engine", engine)
    assert main(["--apply"]) == 2
    engine.assert_not_called()
    output = capsys.readouterr()
    assert "production" in output.err
    assert "password" not in output.err and "secret" not in output.err
    assert json.loads(output.err)["error"] == "input_or_conflict"
    event = [json.loads(line) for line in output.out.splitlines()][-1]
    assert event["event"] == "reference_seed_rejected"
    assert event["dataset_id"] == "mvp-reviewed-v1"
    assert event["dataset_version"] == 1
    assert event["dataset_sha256"] == DATASET_SHA256
    assert event["mode"] == "apply"
    assert event["error_category"] == "input_or_conflict"
    assert isinstance(event["duration_ms"], (int, float))


def test_manifest_tampering_fails_before_repository(monkeypatch):
    from app.application import reference_data_import as application

    original = application.files
    pack = original("app.data.reference")

    class TamperedPack:
        def joinpath(self, name):
            if name == "dataset.json":
                return pack.joinpath(name)
            return Mock(read_bytes=lambda: b'{"invented":"facts"}')

    monkeypatch.setattr(application, "files", lambda _: TamperedPack())
    with pytest.raises(ReferenceDataConflict, match="digest mismatch"):
        load_dataset()


def test_duplicate_keys_rejected():
    with pytest.raises(ReferenceDataConflict):
        _bounded_json(b'{"field":1,"field":1}')


def test_database_failure_is_safe_operational_error(monkeypatch, capsys):
    from sqlalchemy.exc import OperationalError

    from app.cli import seed_reference_data as cli

    monkeypatch.setattr(
        cli,
        "get_settings",
        lambda: Settings(
            _env_file=None,
            app_env="test",
            database_url="postgresql+psycopg://private_user:private_password@localhost:5432/benefits?token=secret",
        ),
    )

    def unavailable(_settings):
        raise OperationalError("secret SQL", {}, RuntimeError("private_password"))

    monkeypatch.setattr(cli, "create_database_engine", unavailable)
    assert main([]) == 3
    output = capsys.readouterr()
    assert json.loads(output.err)["error"] == "database_unavailable"
    assert "private_user" not in output.out + output.err
    assert "private_password" not in output.out + output.err
    assert "secret" not in output.out + output.err
    event = [json.loads(line) for line in output.out.splitlines()][-1]
    assert event["event"] == "reference_seed_failed"
    assert event["error_category"] == "database_unavailable"


def test_cli_emits_plan_and_completion_events(monkeypatch, capsys):
    from app.cli import seed_reference_data as cli

    class SessionStub:
        def __init__(self, _engine):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def begin(self):
            return nullcontext()

        def connection(self):
            class ConnectionStub:
                def exec_driver_sql(self, _statement):
                    pass

            return ConnectionStub()

    class RepositoryStub:
        def __init__(self, _session):
            pass

        def catalogue(self, _dataset, *, apply):
            assert apply is False
            return ()

        def stage(self, _dataset):
            raise AssertionError("plan must not stage promotions")

    monkeypatch.setattr(
        cli,
        "get_settings",
        lambda: Settings(
            _env_file=None, app_env="test", database_url="postgresql://user:pass@localhost/db"
        ),
    )
    monkeypatch.setattr(cli, "create_database_engine", lambda _settings: Mock(dispose=Mock()))
    monkeypatch.setattr(cli, "Session", SessionStub)
    monkeypatch.setattr(cli, "SqlAlchemyReferenceDataRepository", RepositoryStub)
    assert main(["--plan"]) == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines[0]["target"]["database"] == "db"
    assert lines[1]["event"] == "reference_seed_plan"
    assert lines[-1]["event"] == "reference_seed_completed"
    assert lines[-1]["entity_counts"] == {}
    assert lines[-1]["dataset_sha256"] == DATASET_SHA256


def test_schema_mismatch_is_distinct_from_database_unavailable(monkeypatch, capsys):
    from sqlalchemy.exc import ProgrammingError

    from app.cli import seed_reference_data as cli

    monkeypatch.setattr(
        cli,
        "get_settings",
        lambda: Settings(
            _env_file=None, app_env="test", database_url="postgresql://user:pass@localhost/db"
        ),
    )

    def incompatible(_settings):
        error = RuntimeError("private SQL diagnostic")
        error.sqlstate = "42P01"
        raise ProgrammingError("private SQL", {}, error)

    monkeypatch.setattr(cli, "create_database_engine", incompatible)
    assert main([]) == 3
    output = capsys.readouterr()
    assert json.loads(output.err)["error"] == "schema_mismatch"
    assert "private SQL" not in output.err + output.out
    events = [json.loads(line) for line in output.out.splitlines()]
    assert events[-1]["error_category"] == "schema_mismatch"
    assert (
        cli._database_error_category(ProgrammingError("sql", {}, RuntimeError()))
        == "database_error"
    )


def test_schema_mismatch_survives_identity_repository_lookup(monkeypatch, capsys):
    from contextlib import nullcontext

    from sqlalchemy.exc import ProgrammingError

    from app.cli import seed_reference_data as cli

    class DriverError(RuntimeError):
        sqlstate = "42P01"

    class SessionStub:
        no_autoflush = nullcontext()
        new = dirty = deleted = ()

        def __init__(self, _engine):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def begin(self):
            return nullcontext()

        def expire_all(self):
            pass

        def connection(self):
            class ConnectionStub:
                def exec_driver_sql(self, _statement):
                    pass

            return ConnectionStub()

        def execute(self, _statement):
            raise ProgrammingError("private SQL", {}, DriverError("private diagnostic"))

    monkeypatch.setattr(
        cli,
        "get_settings",
        lambda: Settings(
            _env_file=None, app_env="test", database_url="postgresql://user:pass@localhost/db"
        ),
    )
    monkeypatch.setattr(cli, "create_database_engine", lambda _settings: Mock(dispose=Mock()))
    monkeypatch.setattr(cli, "Session", SessionStub)

    assert cli.main([]) == 3
    output = capsys.readouterr()
    assert json.loads(output.err) == {
        "error": "schema_mismatch",
        "message": "Database schema is incompatible; run alembic upgrade head.",
    }
    assert "private" not in output.out + output.err
    events = [json.loads(line) for line in output.out.splitlines()]
    assert events[-1]["event"] == "reference_seed_failed"
    assert events[-1]["error_category"] == "schema_mismatch"


def test_promotion_preflight_runs_before_any_apply_and_rejects_atomically():
    repository = Mock()
    repository.catalogue.return_value = ()
    repository.preview_promotions.side_effect = ReferenceDataConflict("invalid graph")
    with pytest.raises(ReferenceDataConflict, match="invalid graph"):
        import_reference_data(repository, load_dataset(), apply=True, stage_promotions=True)
    assert repository.catalogue.call_args_list == [call(load_dataset(), apply=False)]
    repository.stage.assert_not_called()


def test_preview_is_explicit_and_cannot_apply():
    repository = Mock()
    repository.catalogue.return_value = ()
    repository.preview_promotions.return_value = ()
    report = import_reference_data(repository, load_dataset(), preview_promotions=True)
    assert report.mode == "plan"
    repository.preview_promotions.assert_called_once()
    repository.stage.assert_not_called()
    with pytest.raises(ReferenceDataConflict, match="read-only"):
        import_reference_data(repository, load_dataset(), apply=True, preview_promotions=True)
    assert main(["--apply", "--preview-promotions"]) == 2
