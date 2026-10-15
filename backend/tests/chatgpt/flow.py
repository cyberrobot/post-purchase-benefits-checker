"""Offline scripted decisions and claim assertions; this is not a model client.

No parsing, eligibility calculation, or prose-faithfulness guarantee lives here.
Diagnostics name a scenario/layer, never echo purchase/source text.
"""

import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from jsonschema import ValidationError, validate


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    question: str
    expected_action: Literal["ask_for_missing_details", "call_tool"]
    expected_arguments: dict | None = None
    expected_missing_fields: tuple[str, ...] = ()
    assertion_focus: tuple[str, ...] = ()
    follow_up: str | None = None


@dataclass(frozen=True)
class Claim:
    """A narrow factual assertion, scoped to its original variant and entity."""

    kind: str
    value: object
    variant_id: str | None = None
    entity_id: str | None = None


@dataclass
class ConversationTrace:
    question: str
    selected_tool: str | None = None
    submitted_arguments: dict | None = None
    is_error: bool | None = None
    structured_content: dict | None = None
    claims: tuple[Claim, ...] = ()
    missing_fields: tuple[str, ...] = ()
    failure: str | None = None
    calls: list[tuple[str, dict]] = field(default_factory=list)


def project(data):
    """Copy whitelisted facts; descriptions cannot introduce instructions or rules."""
    claims = [Claim("outcome", data["outcome"])]
    if data["outcome"] == "unresolved_identity":
        claims.append(Claim("unresolved_identity", deepcopy(data["unresolved_identity"])))
        return tuple(claims)
    if not data["promotions"]:
        claims.append(Claim("no_match_reason", data["no_match_reason"]))
    for p in data["promotions"]:
        variant = p["promotion_variant_id"]

        def add(kind, value, entity=None, variant=variant):
            claims.append(Claim(kind, deepcopy(value), variant, entity))

        add("promotion_id", p["promotion_id"])
        add("classification", p["eligibility"]["classification"])
        add("reasons", p["eligibility"]["reasons"])
        add("rule_evaluations", p["eligibility"]["rule_evaluations"])
        add("claim_window", p["claim_window"])
        add("recorded_requirements", p["requirements"])
        add("last_verified_at", p["last_verified_at"])
        add("official_source_url", p["provenance"]["official_source_url"])
        add("claim_url", p["provenance"]["claim_url"])
        for b in p["benefits"]:
            for key in ("cashback_reward_gbp", "reward_unavailable_reason"):
                add(key, b[key], b["benefit_id"])
        for s in p["sources"]:
            add("source", s, s["source_id"])
    return tuple(claims)


def assert_grounded(claims, data):
    allowed = project(data)
    for claim in claims:
        assert claim in allowed, f"result grounding: unsupported {claim.kind}"


class ScriptedConversation:
    """Use an explicit fixture decision, never claim natural-language understanding."""

    def __init__(self, client, tools):
        self.client = client
        self.tools = {tool.name: tool for tool in tools}

    async def run(self, scenario):
        trace = ConversationTrace(scenario.question)
        if scenario.expected_action == "ask_for_missing_details":
            required = set(self.tools["check_purchase"].input_schema["required"])
            assert scenario.expected_missing_fields
            assert set(scenario.expected_missing_fields) <= required
            assert scenario.expected_arguments is None
            trace.missing_fields = scenario.expected_missing_fields
            return trace
        trace.selected_tool = "check_purchase"
        trace.submitted_arguments = scenario.expected_arguments
        data = await self.dispatch(trace, "check_purchase", scenario.expected_arguments)
        if data is not None:
            trace.structured_content = data
            trace.claims = project(data)
            assert_grounded(trace.claims, data)
        return trace

    async def dispatch(self, trace, name, arguments):
        if name not in self.tools:
            trace.failure = "tool dispatch: unknown_tool"
            return None
        trace.calls.append((name, arguments))
        try:
            result = await self.client.call_tool(name, arguments)
        except Exception:
            trace.failure = "tool dispatch: unavailable"
            return None
        trace.is_error = result.is_error
        if result.is_error:
            # Error text is not a successful payload, even if it resembles JSON data.
            trace.failure = "backend contract: tool_error"
            return None
        try:
            validate(result.structured_content, self.tools[name].output_schema)
        except (ValidationError, TypeError):
            trace.failure = "backend contract: invalid_structured_content"
            return None
        data = result.structured_content
        if name == "check_purchase" and data["outcome"] == "resolved":
            if any(
                p["last_verified_at"] != p["provenance"]["verified_at"] for p in data["promotions"]
            ):
                trace.failure = "backend contract: contradictory_verification"
                return None
        return data

    async def detail(self, trace, name, arguments):
        """Scope a follow-up to the original published response, not arbitrary IDs.

        Detail snapshots can be newer. They never replace purchase verdict/rewards.
        """
        if not trace.structured_content or trace.structured_content["outcome"] != "resolved":
            raise AssertionError("tool dispatch: no purchase evidence")
        promotions = trace.structured_content["promotions"]
        p = next(
            (
                p
                for p in promotions
                if p["promotion_variant_id"] == arguments.get("promotion_variant_id")
            ),
            None,
        )
        assert p is not None, "tool dispatch: unreturned variant"
        assert name in {"get_benefit", "get_claim_requirements", "get_promotion_source"}, (
            "tool dispatch: invalid supporting tool"
        )
        for tool, key, collection in (
            ("get_benefit", "benefit_id", "benefits"),
            ("get_promotion_source", "source_id", "sources"),
        ):
            if name == tool:
                assert arguments.get(key) in {v[key] for v in p[collection]}, (
                    "tool dispatch: unreturned association"
                )
        if arguments.get("product_id") is not None:
            assert (
                arguments["product_id"]
                == trace.structured_content["resolved_identity"]["product_id"]
            ), "tool dispatch: unreturned product"
        result = await self.dispatch(trace, name, arguments)
        if result is not None:
            assert result["promotion_variant_id"] == p["promotion_variant_id"]
            assert result["promotion_id"] == p["promotion_id"]
            for key in ("benefit_id", "source_id"):
                if key in arguments:
                    assert result[key] == arguments[key], "backend contract: wrong association"
            if name == "get_claim_requirements":
                assert result["requirements_recorded"] == bool(result["requirements"]), (
                    "backend contract: contradictory requirements"
                )
        return result


def safe_error_code(result):
    assert result.is_error and result.structured_content is None
    envelope = json.loads(result.content[0].text)
    assert set(envelope) == {"code", "message", "request_id"}
    UUID(envelope["request_id"])
    return envelope["code"]
