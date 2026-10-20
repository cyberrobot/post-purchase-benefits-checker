"""Seeded catalogue through real REST/MCP reads and explicit test publication."""

import asyncio
from datetime import date
from functools import partial

import httpx2
import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.api.eligibility import uk_evaluation_date
from app.application.promotions import change_promotion_status
from app.core.config import Settings
from app.db.models import Manufacturer, Product, Promotion, Retailer, RetailerAlias, Source
from app.db.repositories.promotions import promotion_transaction
from app.domain.promotion_lifecycle import PromotionStatus
from app.main import create_app
from app.mcp import server as adapter
from tests.integration.test_reference_data_import import run
from tests.integration.test_sony_reference_promotion import delete_owned_rows
from tests.unit.test_mcp_check_purchase import protocol_client

pytestmark = pytest.mark.integration


def test_seeded_rest_mcp_publication_journey(postgres_engine, migrated_test_database, monkeypatch):
    factory = sessionmaker(postgres_engine)
    kinds = (Promotion, Source, Product, Retailer, Manufacturer)
    with factory() as session:
        before = {kind: set(session.scalars(select(kind.id))) for kind in kinds}
        before_aliases = set(
            session.execute(select(RetailerAlias.retailer_id, RetailerAlias.normalised_alias))
        )
    app = create_app(
        Settings(
            _env_file=None,
            app_env="test",
            database_url="postgresql+psycopg://unused/db",
            mcp_http_enabled=True,
        ),
        engine_factory=lambda _: postgres_engine,
    )
    app.dependency_overrides[uk_evaluation_date] = lambda: date(2026, 11, 27)
    monkeypatch.setattr(adapter, "uk_evaluation_date", lambda: date(2026, 11, 27))

    async def journey():
        async with app.router.lifespan_context(app), protocol_client(app) as client:
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://localhost:8000"
            ) as http:
                body = {
                    "brand": "Samsung",
                    "model": "Blah",
                    "retailer": "Currys",
                    "purchase_date": "2026-10-19",
                }

                async def check(arguments):
                    response = await http.post("/api/v1/eligibility/check", json=arguments)
                    assert response.status_code == 200
                    mcp = await client.call_tool("check_purchase", arguments)
                    assert not mcp.is_error
                    assert mcp.structured_content == response.json()
                    return response.json()

                empty = await check(body)
                assert empty["outcome"] == "unresolved_identity"
                assert empty["unresolved_identity"]["field"] == "brand"
                with factory.begin() as session:
                    run(session)
                seeded = await check(body)
                assert seeded["unresolved_identity"] == {
                    "field": "model",
                    "status": "not_found",
                    "candidate_ids": [],
                }
                known = {
                    "brand": "Hisense",
                    "model": "WF7I1248BBR",
                    "retailer": "Currys",
                    "purchase_date": "2026-10-19",
                }
                result = await check(known)
                assert result["outcome"] == "resolved" and result["promotions"] == []
                assert result["no_match_reason"] == "no_matching_published_promotions"
                with factory.begin() as session:
                    run(session, stage=True)
                    promotion_id = session.scalar(
                        select(Promotion.id)
                        .join(Manufacturer)
                        .where(Manufacturer.slug == "hisense")
                    )
                assert (await check(known))["promotions"] == []
                change_promotion_status(
                    partial(promotion_transaction, factory), promotion_id, PromotionStatus.ACTIVE
                )
                published = await check(known)
                assert len(published["promotions"]) == 1
                assert published["promotions"][0]["eligibility"]["classification"] == "ELIGIBLE"

    try:
        asyncio.run(journey())
    finally:
        with factory.begin() as session:
            owned = {kind: set(session.scalars(select(kind.id))) - before[kind] for kind in kinds}
            owned[RetailerAlias] = (
                set(
                    session.execute(
                        select(RetailerAlias.retailer_id, RetailerAlias.normalised_alias)
                    )
                )
                - before_aliases
            )
            delete_owned_rows(session, owned)
