import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def test_committed_test_data_is_rolled_back_before_the_next_session(db_session_factory) -> None:
    with db_session_factory() as first_test_session:
        first_test_session.execute(
            text("INSERT INTO test_session_isolation_probe (marker) VALUES ('first-test')")
        )
        first_test_session.commit()
        assert (
            first_test_session.execute(
                text("SELECT count(*) FROM test_session_isolation_probe")
            ).scalar_one()
            == 1
        )

    with db_session_factory() as second_test_session:
        assert (
            second_test_session.execute(
                text("SELECT count(*) FROM test_session_isolation_probe")
            ).scalar_one()
            == 0
        )

    with pytest.raises(RuntimeError, match="test failed"):
        with db_session_factory() as failed_test_session:
            failed_test_session.execute(
                text("INSERT INTO test_session_isolation_probe (marker) VALUES ('failed-test')")
            )
            raise RuntimeError("test failed")

    with db_session_factory() as following_test_session:
        assert (
            following_test_session.execute(
                text("SELECT count(*) FROM test_session_isolation_probe")
            ).scalar_one()
            == 0
        )


def test_per_test_session_fixture_is_reusable(db_session: Session) -> None:
    assert (
        db_session.execute(text("SELECT count(*) FROM test_session_isolation_probe")).scalar_one()
        == 0
    )
