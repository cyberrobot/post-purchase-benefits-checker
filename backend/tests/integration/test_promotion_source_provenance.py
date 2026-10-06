from functools import partial

import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.application.promotions import PromotionPersistenceError, change_promotion_status
from app.db.models import PromotionSource, Source
from app.db.repositories.promotions import SqlAlchemyPromotionRepository, promotion_transaction
from app.domain.promotion_lifecycle import PromotionStatus as S
from app.domain.promotion_provenance import PromotionProvenanceError, SourceRole, SourceType
from tests.integration.test_core_promotion_schema import graph as complete_graph  # noqa: F401
from tests.integration.test_promotion_lifecycle import snapshot, transaction

pytestmark = pytest.mark.integration


@pytest.fixture
def graph(request):
    return request.getfixturevalue("complete_graph")


@pytest.mark.parametrize("target", [S.EXPIRED, S.ARCHIVED])
def test_publication_and_retirement_preserve_evidence(db_session, graph, target):
    graph.status = S.REVIEW
    db_session.flush()
    before = snapshot(db_session)
    repository = SqlAlchemyPromotionRepository(db_session)
    records = repository.list_promotion_sources(graph.id)
    assert {r.role for r in records} == set(SourceRole)
    assert all(r.source_type == SourceType.WEB_PAGE for r in records)
    assert all(r.verified_at == r.retrieved_at for r in records)
    assert change_promotion_status(partial(transaction, db_session), graph.id, S.ACTIVE).changed
    assert change_promotion_status(partial(transaction, db_session), graph.id, target).changed
    after = snapshot(db_session)
    for table in before.keys() - {"promotions"}:
        assert before[table] == after[table]
    assert repository.get_promotion(graph.id).status == target


@pytest.mark.parametrize("role", ["primary", "claim"])
@pytest.mark.parametrize("case", ["missing", "ambiguous", "unverified", "invalid_url"])
def test_rejected_publication_and_corrected_retry(db_session, graph, role, case):
    graph.status = S.REVIEW
    link = next(link for link in graph.source_links if link.role == role)
    extra = None
    if case == "missing":
        link.role = "supporting"
        reason = f"missing_{role}_source"
    elif case == "ambiguous":
        extra = PromotionSource(
            promotion=graph,
            role=role,
            source=Source(
                url=link.source.url,
                source_type="pdf",
                retrieved_at=link.source.retrieved_at,
                verified_at=link.source.verified_at,
            ),
        )
        db_session.add(extra)
        reason = f"ambiguous_{role}_source"
    elif case == "unverified":
        link.source.verified_at = None
        reason = f"{role}_source_unverified"
    else:
        link.source.url = "relative/path"
        reason = f"invalid_{role}_url"
    db_session.flush()
    before = snapshot(db_session)
    statements = []

    def capture(connection, cursor, statement, *args):
        statements.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", capture)
    try:
        with pytest.raises(PromotionProvenanceError) as error:
            change_promotion_status(partial(transaction, db_session), graph.id, S.ACTIVE)
        assert error.value.reason_code == reason
    finally:
        event.remove(db_session.bind, "before_cursor_execute", capture)
    assert not any(s.lstrip().upper().startswith("UPDATE") for s in statements)
    assert snapshot(db_session) == before
    assert SqlAlchemyPromotionRepository(db_session).get_promotion(graph.id).status == S.REVIEW
    link.role = role
    link.source.url = "https://example.test/promotion"
    link.source.verified_at = link.source.retrieved_at
    if extra is not None:
        db_session.delete(extra)
    db_session.flush()
    assert change_promotion_status(partial(transaction, db_session), graph.id, S.ACTIVE).changed


@pytest.mark.parametrize("stage", ["query", "update", "commit"])
def test_publication_database_failure_rolls_back(db_session, graph, stage):
    graph.status = S.REVIEW
    db_session.flush()
    identity = graph.id
    before = snapshot(db_session)

    def fail_statement(connection, cursor, statement, *args):
        if (stage == "query" and "JOIN promotion_sources" in statement) or (
            stage == "update" and statement.startswith("UPDATE promotions")
        ):
            raise OperationalError("private SQL", {}, Exception("private detail"))

    def fail_commit(*args):
        raise OperationalError("private SQL", {}, Exception("private detail"))

    def factory():
        return Session(bind=db_session.connection(), join_transaction_mode="create_savepoint")

    event.listen(db_session.bind, "before_cursor_execute", fail_statement)
    if stage == "commit":
        event.listen(Session, "before_commit", fail_commit)
    try:
        with pytest.raises(PromotionPersistenceError) as error:
            change_promotion_status(partial(promotion_transaction, factory), identity, S.ACTIVE)
        assert "private" not in str(error.value)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", fail_statement)
        if stage == "commit":
            event.remove(Session, "before_commit", fail_commit)
    assert snapshot(db_session) == before


@pytest.mark.parametrize("source_type", list(SourceType))
def test_classification_round_trip(db_session, graph, source_type):
    graph.source_links[0].source.source_type = source_type.value
    db_session.flush()
    records = SqlAlchemyPromotionRepository(db_session).list_promotion_sources(graph.id)
    assert source_type in {record.source_type for record in records}
